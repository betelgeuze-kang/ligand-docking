#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPERVISED_DATASET_JSON = "runs/residual_production_supervised_dataset_current.json"
DEFAULT_VALIDATION_JSON = "runs/residual_energy_force_label_validation_current.json"
DEFAULT_PDBBIND_PREFLIGHT_JSON = "runs/pdbbind_casf_pose_affinity_product_preflight_current.json"
DEFAULT_FORCE_ARTIFACT_RECOVERY_WORK_ORDER_JSON = "runs/residual_force_artifact_recovery_work_order_current.json"
DEFAULT_FORCE_TRAJECTORY_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_FORCE_TRAJECTORY_REGENERATION_EXECUTION_PROBE_JSON = (
    "runs/residual_force_trajectory_regeneration_execution_probe_current.json"
)
DEFAULT_FORCE_GPU_WORKER_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_FORCE_GPU_WORKER_RETURN_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_OUT_JSON = "runs/residual_energy_force_label_evidence_work_order_current.json"
DEFAULT_OUT_CSV = "runs/residual_energy_force_label_evidence_work_order_current.csv"
DEFAULT_OUT_MD = "runs/residual_energy_force_label_evidence_work_order_current.md"

ENERGY_PROXY_COLUMNS = (
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
    "physics_favorable_energy_proxy",
    "mean_e_vdw",
    "mean_e_polar",
    "mean_e_nonpolar",
    "mean_e_solvation",
)
FORCE_LABEL_COLUMN_TOKENS = ("force", "gradient")

CLAIM_BOUNDARY = (
    "Residual energy/force label evidence work order only; inspects existing local supervised rows, matching stage3 "
    "score artifacts, and optional validation evidence for production delta_energy/delta_force label closure. It does "
    "not run docking, compute new energy labels, derive forces, train models, create checkpoints, promote production "
    "mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


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


def _bool(value: Any) -> bool:
    return value is True


def _float_present(value: Any) -> bool:
    try:
        if value is None or str(value).strip() == "":
            return False
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _valid_path_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    return text


def _stage3_path_from_stage5(source_csv: str) -> Path:
    source = _resolve(source_csv)
    name = source.name
    if name.endswith("_stage5_ranking_rows.csv"):
        return source.with_name(name.replace("_stage5_ranking_rows.csv", "_stage3_scores.csv"))
    return source


def _work_row(
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
        "label_materialized": False,
        "validation_executed": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _scan_stage3_source(
    path: Path,
    supervised_keys: set[tuple[str, str]],
    *,
    max_rows_per_source: int,
) -> dict[str, Any]:
    scanned_rows = 0
    joined_rows = 0
    energy_proxy_rows = 0
    force_label_rows = 0
    trajectory_npz_rows = 0
    backmapped_pdb_rows = 0
    energy_proxy_keys: set[str] = set()
    force_label_keys: set[str] = set()
    if not path.exists():
        return {
            "source_csv": _rel(path),
            "status": "missing_stage3_source",
            "scanned_rows": 0,
            "joined_supervised_rows": 0,
            "energy_proxy_rows": 0,
            "force_label_rows": 0,
            "trajectory_npz_rows": 0,
            "backmapped_pdb_rows": 0,
            "energy_proxy_columns": "",
            "force_label_columns": "",
        }
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            fields = set(fieldnames)
            energy_cols = [col for col in ENERGY_PROXY_COLUMNS if col in fields]
            force_cols = [
                col
                for col in fieldnames
                if any(token in col.lower() for token in FORCE_LABEL_COLUMN_TOKENS)
                and not col.lower().startswith(("force_backend",))
            ]
            if "target" not in fields or "ligand_id" not in fields:
                return {
                    "source_csv": _rel(path),
                    "status": "skipped_missing_join_columns",
                    "scanned_rows": 0,
                    "joined_supervised_rows": 0,
                    "energy_proxy_rows": 0,
                    "force_label_rows": 0,
                    "trajectory_npz_rows": 0,
                    "backmapped_pdb_rows": 0,
                    "energy_proxy_columns": ",".join(energy_cols),
                    "force_label_columns": ",".join(force_cols),
                }
            for raw in reader:
                scanned_rows += 1
                if scanned_rows > max_rows_per_source:
                    break
                key = (str(raw.get("target") or "").strip(), str(raw.get("ligand_id") or "").strip())
                if key not in supervised_keys:
                    continue
                joined_rows += 1
                if any(_float_present(raw.get(col)) for col in energy_cols):
                    energy_proxy_rows += 1
                    energy_proxy_keys.add(f"{key[0]}::{key[1]}")
                if any(_float_present(raw.get(col)) for col in force_cols):
                    force_label_rows += 1
                    force_label_keys.add(f"{key[0]}::{key[1]}")
                if _valid_path_text(raw.get("trajectory_npz")):
                    trajectory_npz_rows += 1
                if _valid_path_text(raw.get("backmapped_pdb")):
                    backmapped_pdb_rows += 1
    except OSError as exc:
        return {
            "source_csv": _rel(path),
            "status": f"read_error:{exc}",
            "scanned_rows": scanned_rows,
            "joined_supervised_rows": joined_rows,
            "energy_proxy_rows": energy_proxy_rows,
            "force_label_rows": force_label_rows,
            "trajectory_npz_rows": trajectory_npz_rows,
            "backmapped_pdb_rows": backmapped_pdb_rows,
            "energy_proxy_columns": "",
            "force_label_columns": "",
        }
    status = "used" if joined_rows else "no_joined_supervised_rows"
    return {
        "source_csv": _rel(path),
        "status": status,
        "scanned_rows": min(scanned_rows, max_rows_per_source),
        "joined_supervised_rows": joined_rows,
        "energy_proxy_rows": energy_proxy_rows,
        "force_label_rows": force_label_rows,
        "trajectory_npz_rows": trajectory_npz_rows,
        "backmapped_pdb_rows": backmapped_pdb_rows,
        "energy_proxy_columns": ",".join(energy_cols),
        "force_label_columns": ",".join(force_cols),
        "_energy_proxy_keys": sorted(energy_proxy_keys),
        "_force_label_keys": sorted(force_label_keys),
    }


def build_residual_energy_force_label_evidence_work_order(
    *,
    supervised_dataset_packet: dict[str, Any],
    validation_packet: dict[str, Any] | None = None,
    pdbbind_preflight_packet: dict[str, Any] | None = None,
    force_artifact_recovery_work_order_packet: dict[str, Any] | None = None,
    force_trajectory_regeneration_queue_packet: dict[str, Any] | None = None,
    force_trajectory_regeneration_execution_probe_packet: dict[str, Any] | None = None,
    force_gpu_worker_handoff_packet: dict[str, Any] | None = None,
    force_gpu_worker_return_receipt_packet: dict[str, Any] | None = None,
    supervised_dataset_path: str = DEFAULT_SUPERVISED_DATASET_JSON,
    validation_path: str = DEFAULT_VALIDATION_JSON,
    pdbbind_preflight_path: str = DEFAULT_PDBBIND_PREFLIGHT_JSON,
    force_artifact_recovery_work_order_path: str = DEFAULT_FORCE_ARTIFACT_RECOVERY_WORK_ORDER_JSON,
    force_trajectory_regeneration_queue_path: str = DEFAULT_FORCE_TRAJECTORY_REGENERATION_QUEUE_JSON,
    force_trajectory_regeneration_execution_probe_path: str = DEFAULT_FORCE_TRAJECTORY_REGENERATION_EXECUTION_PROBE_JSON,
    force_gpu_worker_handoff_path: str = DEFAULT_FORCE_GPU_WORKER_HANDOFF_JSON,
    force_gpu_worker_return_receipt_path: str = DEFAULT_FORCE_GPU_WORKER_RETURN_RECEIPT_JSON,
    min_energy_proxy_rows: int = 1000,
    max_sources: int = 24,
    max_rows_per_source: int = 20000,
) -> dict[str, Any]:
    supervised = _summary(supervised_dataset_packet)
    validation = _summary(validation_packet or {})
    pdbbind = _summary(pdbbind_preflight_packet or {})
    force_recovery = _summary(force_artifact_recovery_work_order_packet or {})
    force_regeneration_queue = _summary(force_trajectory_regeneration_queue_packet or {})
    force_regeneration_probe = _summary(force_trajectory_regeneration_execution_probe_packet or {})
    force_gpu_handoff = _summary(force_gpu_worker_handoff_packet or {})
    force_gpu_return_receipt = _summary(force_gpu_worker_return_receipt_packet or {})
    supervised_rows = [
        dict(row) for row in supervised_dataset_packet.get("rows", []) or [] if isinstance(row, dict)
    ]
    supervised_keys = {
        (str(row.get("target") or "").strip(), str(row.get("ligand_id") or "").strip())
        for row in supervised_rows
        if str(row.get("target") or "").strip() and str(row.get("ligand_id") or "").strip()
    }
    stage5_sources = sorted({str(row.get("source_csv") or "").strip() for row in supervised_rows if row.get("source_csv")})
    stage3_paths = []
    seen_paths: set[str] = set()
    for source in stage5_sources:
        stage3 = _stage3_path_from_stage5(source)
        key = str(stage3)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        stage3_paths.append(stage3)
    source_rows = [
        _scan_stage3_source(path, supervised_keys, max_rows_per_source=max_rows_per_source)
        for path in stage3_paths[: max(0, max_sources)]
    ]

    energy_proxy_rows = sum(int(row.get("energy_proxy_rows") or 0) for row in source_rows)
    energy_proxy_key_count = len(
        {
            str(key)
            for row in source_rows
            for key in row.get("_energy_proxy_keys", [])
            if str(key)
        }
    )
    joined_rows = sum(int(row.get("joined_supervised_rows") or 0) for row in source_rows)
    force_label_rows = sum(int(row.get("force_label_rows") or 0) for row in source_rows)
    force_label_key_count = len(
        {
            str(key)
            for row in source_rows
            for key in row.get("_force_label_keys", [])
            if str(key)
        }
    )
    trajectory_npz_rows = sum(int(row.get("trajectory_npz_rows") or 0) for row in source_rows)
    backmapped_pdb_rows = sum(int(row.get("backmapped_pdb_rows") or 0) for row in source_rows)
    missing_labels = [str(field) for field in supervised.get("missing_production_output_labels") or []]
    label_fields = [str(field) for field in supervised.get("label_fields") or []]
    validation_joined_energy_proxy_pair_count = int(validation.get("joined_energy_proxy_pair_count") or 0)
    validation_stage3_energy_proxy_pair_count = int(validation.get("stage3_energy_proxy_pair_count") or 0)
    validation_embedded_delta_energy_proxy_pair_count = int(
        validation.get("embedded_delta_energy_proxy_pair_count") or 0
    )
    validation_energy_proxy_source_mode = str(validation.get("energy_proxy_source_mode") or "")
    stage3_energy_proxy_candidate_ready = energy_proxy_key_count >= min_energy_proxy_rows
    embedded_energy_proxy_candidate_ready = (
        validation_embedded_delta_energy_proxy_pair_count >= min_energy_proxy_rows
        and validation_energy_proxy_source_mode in {
            "embedded_supervised_delta_energy_proxy",
            "stage3_score_artifacts_plus_embedded_supervised_delta_energy_proxy",
        }
    )
    energy_proxy_candidate_ready = stage3_energy_proxy_candidate_ready or embedded_energy_proxy_candidate_ready
    energy_validation_ready = _bool(validation.get("delta_energy_proxy_validation_ready"))
    force_validation_ready = _bool(validation.get("delta_force_derivation_validation_ready"))
    validation_blockers = [str(item) for item in validation.get("blockers") or []]
    force_derivation_valid_trajectory_path_rows = int(validation.get("force_derivation_valid_trajectory_path_rows") or 0)
    force_derivation_existing_trajectory_npz_rows = int(validation.get("force_derivation_existing_trajectory_npz_rows") or 0)
    force_derivation_input_sample_count = int(validation.get("force_derivation_input_sample_count") or 0)
    force_derivation_effective_min_existing_npz_rows = int(
        validation.get("force_derivation_effective_min_existing_npz_rows")
        or validation.get("effective_min_existing_npz_rows")
        or 0
    )
    force_derivation_existing_npz_floor_capped = _bool(
        validation.get("force_derivation_existing_npz_floor_capped_by_available_paths")
        if "force_derivation_existing_npz_floor_capped_by_available_paths" in validation
        else validation.get("existing_npz_floor_capped_by_available_paths")
    )
    force_derivation_next_required_step = str(validation.get("force_derivation_next_required_step") or "")
    force_artifact_recovery_required = _bool(force_recovery.get("force_artifact_recovery_required"))
    force_artifact_missing_trajectory_npz_rows = int(force_recovery.get("missing_trajectory_npz_rows") or 0)
    force_artifact_top_missing_prefix = str(force_recovery.get("top_missing_prefix") or "")
    force_artifact_top_missing_source = str(force_recovery.get("top_missing_source") or "")
    force_artifact_recovery_next_required_step = str(force_recovery.get("next_required_step") or "")
    force_trajectory_regeneration_queue_ready = _bool(force_regeneration_queue.get("regeneration_queue_ready"))
    force_trajectory_regeneration_queue_execution_ready = _bool(
        force_regeneration_queue.get("regeneration_queue_execution_ready")
    )
    force_trajectory_regeneration_queue_rows = int(force_regeneration_queue.get("queue_rows") or 0)
    force_trajectory_regeneration_queue_command = str(force_regeneration_queue.get("engine_command") or "")
    force_trajectory_regeneration_engine_runtime_ready = _bool(force_regeneration_probe.get("engine_runtime_ready"))
    force_trajectory_regeneration_gpu_backend_unavailable = _bool(
        force_regeneration_probe.get("gpu_backend_unavailable")
    )
    force_trajectory_regeneration_pilot_abort_reason = str(force_regeneration_probe.get("pilot_abort_reason") or "")
    force_gpu_worker_handoff_ready = _bool(force_gpu_handoff.get("gpu_worker_handoff_ready"))
    force_gpu_worker_handoff_required = _bool(force_gpu_handoff.get("gpu_worker_handoff_required"))
    force_gpu_worker_handoff_next_required_step = str(force_gpu_handoff.get("next_required_step") or "")
    force_gpu_worker_return_receipt_ready = _bool(force_gpu_return_receipt.get("gpu_worker_return_receipt_ready"))
    force_gpu_worker_return_receipt_blockers = [
        str(item) for item in force_gpu_return_receipt.get("blockers") or []
    ]
    force_gpu_worker_return_summary_manifest_bound = _bool(
        force_gpu_return_receipt.get("full_regeneration_summary_manifest_bound")
    )
    force_gpu_worker_return_summary_manifest_csv = str(
        force_gpu_return_receipt.get("summary_manifest_csv") or ""
    )
    force_gpu_worker_return_summary_out_manifest_csv_present = _bool(
        force_gpu_return_receipt.get("full_regeneration_summary_out_manifest_csv_present")
    )
    force_gpu_worker_return_summary_out_manifest_csv = str(
        force_gpu_return_receipt.get("summary_out_manifest_csv") or ""
    )
    force_gpu_worker_return_summary_out_manifest_csv_bound = _bool(
        force_gpu_return_receipt.get("full_regeneration_summary_out_manifest_csv_bound")
    )
    force_gpu_worker_return_summary_out_summary_json_bound = _bool(
        force_gpu_return_receipt.get("full_regeneration_summary_out_summary_json_bound")
    )
    force_gpu_worker_return_summary_out_summary_json = str(
        force_gpu_return_receipt.get("summary_out_summary_json") or ""
    )
    force_gpu_worker_return_summary_manifest_row_counts_consistent = _bool(
        force_gpu_return_receipt.get("full_regeneration_summary_manifest_row_counts_consistent")
    )
    force_gpu_worker_return_receipt_next_required_step = str(
        force_gpu_return_receipt.get("next_required_step") or ""
    ) or (
        "Return GPU full-regeneration summary/manifest, rebuild residual_force_gpu_worker_return_receipt, "
        "then rerun force-derivation validation."
    )
    force_gpu_worker_return_identity_coverage_ready = _bool(
        force_gpu_return_receipt.get("queue_manifest_identity_coverage_ready")
    )
    force_gpu_worker_return_matched_queue_id_count = int(
        force_gpu_return_receipt.get("manifest_matched_queue_id_count") or 0
    )
    force_gpu_worker_return_matched_expected_npz_count = int(
        force_gpu_return_receipt.get("manifest_matched_expected_npz_count") or 0
    )
    force_gpu_worker_return_missing_queue_id_count = int(
        force_gpu_return_receipt.get("missing_queue_id_count") or 0
    )
    force_gpu_worker_return_missing_expected_npz_count = int(
        force_gpu_return_receipt.get("missing_expected_npz_count") or 0
    )
    force_gpu_worker_return_manifest_status_placeholder_count = int(
        force_gpu_return_receipt.get("manifest_status_placeholder_count") or 0
    )
    force_gpu_worker_return_manifest_status_invalid_count = int(
        force_gpu_return_receipt.get("manifest_status_invalid_count") or 0
    )
    force_gpu_worker_return_manifest_allowed_ok_status_values = [
        str(item) for item in force_gpu_return_receipt.get("manifest_allowed_ok_status_values") or []
    ]
    force_gpu_worker_return_manifest_npz_paths_complete = _bool(
        force_gpu_return_receipt.get("full_regeneration_manifest_npz_paths_complete")
    )
    force_gpu_worker_return_manifest_npz_path_present_count = int(
        force_gpu_return_receipt.get("manifest_npz_path_present_count") or 0
    )
    force_gpu_worker_return_manifest_npz_path_missing_count = int(
        force_gpu_return_receipt.get("manifest_npz_path_missing_count") or 0
    )
    force_gpu_worker_return_manifest_ok_row_missing_npz_path_count = int(
        force_gpu_return_receipt.get("manifest_ok_row_missing_npz_path_count") or 0
    )
    force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count = int(
        force_gpu_return_receipt.get("manifest_operator_verified_missing_npz_path_count") or 0
    )
    force_gpu_worker_return_manifest_npz_files_exist = _bool(
        force_gpu_return_receipt.get("full_regeneration_manifest_npz_files_exist")
    )
    force_gpu_worker_return_manifest_npz_file_existing_count = int(
        force_gpu_return_receipt.get("manifest_npz_file_existing_count") or 0
    )
    force_gpu_worker_return_manifest_npz_file_missing_count = int(
        force_gpu_return_receipt.get("manifest_npz_file_missing_count") or 0
    )
    force_gpu_worker_return_manifest_ok_row_missing_npz_file_count = int(
        force_gpu_return_receipt.get("manifest_ok_row_missing_npz_file_count") or 0
    )
    force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count = int(
        force_gpu_return_receipt.get("manifest_operator_verified_missing_npz_file_count") or 0
    )
    force_gpu_worker_return_manifest_npz_files_valid = _bool(
        force_gpu_return_receipt.get("full_regeneration_manifest_npz_files_valid")
    )
    force_gpu_worker_return_manifest_npz_file_valid_count = int(
        force_gpu_return_receipt.get("manifest_npz_file_valid_count") or 0
    )
    force_gpu_worker_return_manifest_npz_file_invalid_count = int(
        force_gpu_return_receipt.get("manifest_npz_file_invalid_count") or 0
    )
    force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count = int(
        force_gpu_return_receipt.get("manifest_ok_row_invalid_npz_file_count") or 0
    )
    force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count = int(
        force_gpu_return_receipt.get("manifest_operator_verified_invalid_npz_file_count") or 0
    )
    force_gpu_worker_return_manifest_npz_schema_valid = _bool(
        force_gpu_return_receipt.get("full_regeneration_manifest_npz_schema_valid")
    )
    force_gpu_worker_return_manifest_npz_schema_valid_count = int(
        force_gpu_return_receipt.get("manifest_npz_schema_valid_count") or 0
    )
    force_gpu_worker_return_manifest_npz_schema_invalid_count = int(
        force_gpu_return_receipt.get("manifest_npz_schema_invalid_count") or 0
    )
    force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count = int(
        force_gpu_return_receipt.get("manifest_ok_row_invalid_npz_schema_count") or 0
    )
    force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count = int(
        force_gpu_return_receipt.get("manifest_operator_verified_invalid_npz_schema_count") or 0
    )
    force_gpu_worker_return_manifest_npz_identity_valid = _bool(
        force_gpu_return_receipt.get("full_regeneration_manifest_npz_identity_valid")
    )
    force_gpu_worker_return_manifest_npz_identity_valid_count = int(
        force_gpu_return_receipt.get("manifest_npz_identity_valid_count") or 0
    )
    force_gpu_worker_return_manifest_npz_identity_invalid_count = int(
        force_gpu_return_receipt.get("manifest_npz_identity_invalid_count") or 0
    )
    force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count = int(
        force_gpu_return_receipt.get("manifest_ok_row_invalid_npz_identity_count") or 0
    )
    force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count = int(
        force_gpu_return_receipt.get("manifest_operator_verified_invalid_npz_identity_count") or 0
    )
    force_derivation_input_ready = bool(trajectory_npz_rows and backmapped_pdb_rows and energy_proxy_candidate_ready)
    pdbbind_preflight_ready = _bool(pdbbind.get("product_execution_ready"))
    delta_energy_evidence_ready = "delta_energy" not in missing_labels or (
        energy_proxy_candidate_ready and energy_validation_ready
    )
    delta_force_evidence_ready = "delta_force" not in missing_labels or force_validation_ready
    ready = delta_energy_evidence_ready and delta_force_evidence_ready

    rows = [
        _work_row(
            "delta_energy_proxy_candidate_rows",
            "pass" if energy_proxy_candidate_ready else "fail",
            (
                f"joined_rows={joined_rows};energy_proxy_rows={energy_proxy_rows};"
                f"unique_energy_proxy_keys={energy_proxy_key_count};"
                f"stage3_candidate_ready={stage3_energy_proxy_candidate_ready};"
                f"validation_joined_energy_proxy_pair_count={validation_joined_energy_proxy_pair_count};"
                f"validation_stage3_energy_proxy_pair_count={validation_stage3_energy_proxy_pair_count};"
                f"validation_embedded_delta_energy_proxy_pair_count={validation_embedded_delta_energy_proxy_pair_count};"
                f"validation_energy_proxy_source_mode={validation_energy_proxy_source_mode};"
                f"embedded_candidate_ready={embedded_energy_proxy_candidate_ready};"
                f"min_energy_proxy_rows={min_energy_proxy_rows}"
            ),
            "stage3 energy-proxy rows or embedded supervised stage3 proxy labels join the production residual dataset at target+ligand_id scale",
            supervised_dataset_path,
            (
                "Calibrate or replace the recovered embedded stage3 energy proxy until validation gates pass."
                if embedded_energy_proxy_candidate_ready and not stage3_energy_proxy_candidate_ready
                else "Join stage3 energy proxy columns into the production residual dataset candidate table."
            ),
        ),
        _work_row(
            "delta_energy_proxy_validation",
            "pass" if energy_validation_ready else "fail",
            (
                f"delta_energy_proxy_validation_ready={energy_validation_ready};"
                f"pearson={validation.get('pearson_reference_vs_energy_proxy', 0.0)};"
                f"spearman={validation.get('spearman_reference_vs_energy_proxy', 0.0)};"
                f"rmse={validation.get('rmse_reference_vs_energy_proxy_kcal_mol', 0.0)};"
                f"blockers={','.join(validation_blockers)};"
                f"pdbbind_preflight_ready={pdbbind_preflight_ready}"
            ),
            "validated delta_energy proxy/evaluation evidence is available before treating proxy columns as production labels",
            f"{validation_path};{pdbbind_preflight_path}",
            str(
                validation.get("next_required_step")
                or "Validate the energy proxy against staged public pose/affinity evidence or an approved physics benchmark, then write residual_energy_force_label_validation_current.json."
            ),
        ),
        _work_row(
            "delta_force_label_or_derivation_evidence",
            "pass" if delta_force_evidence_ready else "fail",
            (
                f"force_label_rows={force_label_rows};unique_force_label_keys={force_label_key_count};"
                f"trajectory_npz_rows={trajectory_npz_rows};"
                f"backmapped_pdb_rows={backmapped_pdb_rows};"
                f"valid_trajectory_path_rows={force_derivation_valid_trajectory_path_rows};"
                f"existing_trajectory_npz_rows={force_derivation_existing_trajectory_npz_rows};"
                f"derivation_input_sample_count={force_derivation_input_sample_count};"
                f"effective_min_existing_npz_rows={force_derivation_effective_min_existing_npz_rows};"
                f"existing_npz_floor_capped_by_available_paths={force_derivation_existing_npz_floor_capped};"
                f"artifact_recovery_required={force_artifact_recovery_required};"
                f"missing_trajectory_npz_rows={force_artifact_missing_trajectory_npz_rows};"
                f"top_missing_prefix={force_artifact_top_missing_prefix};"
                f"trajectory_regeneration_queue_ready={force_trajectory_regeneration_queue_ready};"
                f"trajectory_regeneration_queue_execution_ready={force_trajectory_regeneration_queue_execution_ready};"
                f"trajectory_regeneration_queue_rows={force_trajectory_regeneration_queue_rows};"
                f"trajectory_regeneration_engine_runtime_ready={force_trajectory_regeneration_engine_runtime_ready};"
                f"trajectory_regeneration_gpu_backend_unavailable={force_trajectory_regeneration_gpu_backend_unavailable};"
                f"trajectory_regeneration_pilot_abort_reason={force_trajectory_regeneration_pilot_abort_reason};"
                f"gpu_worker_handoff_ready={force_gpu_worker_handoff_ready};"
                f"gpu_worker_handoff_required={force_gpu_worker_handoff_required};"
                f"gpu_worker_return_receipt_ready={force_gpu_worker_return_receipt_ready};"
                f"gpu_worker_return_receipt_blockers={','.join(force_gpu_worker_return_receipt_blockers)};"
                f"gpu_worker_return_summary_manifest_bound={force_gpu_worker_return_summary_manifest_bound};"
                f"gpu_worker_return_summary_manifest_csv={force_gpu_worker_return_summary_manifest_csv};"
                f"gpu_worker_return_summary_out_manifest_csv_present={force_gpu_worker_return_summary_out_manifest_csv_present};"
                f"gpu_worker_return_summary_out_manifest_csv={force_gpu_worker_return_summary_out_manifest_csv};"
                f"gpu_worker_return_summary_out_manifest_csv_bound={force_gpu_worker_return_summary_out_manifest_csv_bound};"
                f"gpu_worker_return_summary_out_summary_json_bound={force_gpu_worker_return_summary_out_summary_json_bound};"
                f"gpu_worker_return_summary_out_summary_json={force_gpu_worker_return_summary_out_summary_json};"
                f"gpu_worker_return_summary_manifest_row_counts_consistent={force_gpu_worker_return_summary_manifest_row_counts_consistent};"
                f"gpu_worker_return_summary_ok_rows={force_gpu_return_receipt.get('summary_ok_rows', 0)};"
                f"gpu_worker_return_manifest_ok_row_count={force_gpu_return_receipt.get('manifest_ok_row_count', 0)};"
                f"gpu_worker_return_manifest_status_placeholder_count={force_gpu_worker_return_manifest_status_placeholder_count};"
                f"gpu_worker_return_manifest_status_invalid_count={force_gpu_worker_return_manifest_status_invalid_count};"
                f"gpu_worker_return_manifest_allowed_ok_status_values={','.join(force_gpu_worker_return_manifest_allowed_ok_status_values)};"
                f"gpu_worker_return_manifest_npz_paths_complete={force_gpu_worker_return_manifest_npz_paths_complete};"
                f"gpu_worker_return_manifest_npz_path_present_count={force_gpu_worker_return_manifest_npz_path_present_count};"
                f"gpu_worker_return_manifest_npz_path_missing_count={force_gpu_worker_return_manifest_npz_path_missing_count};"
                f"gpu_worker_return_manifest_ok_row_missing_npz_path_count={force_gpu_worker_return_manifest_ok_row_missing_npz_path_count};"
                f"gpu_worker_return_manifest_operator_verified_missing_npz_path_count={force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count};"
                f"gpu_worker_return_manifest_npz_files_exist={force_gpu_worker_return_manifest_npz_files_exist};"
                f"gpu_worker_return_manifest_npz_file_existing_count={force_gpu_worker_return_manifest_npz_file_existing_count};"
                f"gpu_worker_return_manifest_npz_file_missing_count={force_gpu_worker_return_manifest_npz_file_missing_count};"
                f"gpu_worker_return_manifest_ok_row_missing_npz_file_count={force_gpu_worker_return_manifest_ok_row_missing_npz_file_count};"
                f"gpu_worker_return_manifest_operator_verified_missing_npz_file_count={force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count};"
                f"gpu_worker_return_manifest_npz_files_valid={force_gpu_worker_return_manifest_npz_files_valid};"
                f"gpu_worker_return_manifest_npz_file_valid_count={force_gpu_worker_return_manifest_npz_file_valid_count};"
                f"gpu_worker_return_manifest_npz_file_invalid_count={force_gpu_worker_return_manifest_npz_file_invalid_count};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_file_count={force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_file_count={force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count};"
                f"gpu_worker_return_manifest_npz_schema_valid={force_gpu_worker_return_manifest_npz_schema_valid};"
                f"gpu_worker_return_manifest_npz_schema_valid_count={force_gpu_worker_return_manifest_npz_schema_valid_count};"
                f"gpu_worker_return_manifest_npz_schema_invalid_count={force_gpu_worker_return_manifest_npz_schema_invalid_count};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_schema_count={force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count={force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count};"
                f"gpu_worker_return_manifest_npz_identity_valid={force_gpu_worker_return_manifest_npz_identity_valid};"
                f"gpu_worker_return_manifest_npz_identity_valid_count={force_gpu_worker_return_manifest_npz_identity_valid_count};"
                f"gpu_worker_return_manifest_npz_identity_invalid_count={force_gpu_worker_return_manifest_npz_identity_invalid_count};"
                f"gpu_worker_return_manifest_ok_row_invalid_npz_identity_count={force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count};"
                f"gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count={force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count};"
                f"gpu_worker_return_identity_coverage_ready={force_gpu_worker_return_identity_coverage_ready};"
                f"gpu_worker_return_matched_queue_id_count={force_gpu_worker_return_matched_queue_id_count};"
                f"gpu_worker_return_matched_expected_npz_count={force_gpu_worker_return_matched_expected_npz_count};"
                f"gpu_worker_return_missing_queue_id_count={force_gpu_worker_return_missing_queue_id_count};"
                f"gpu_worker_return_missing_expected_npz_count={force_gpu_worker_return_missing_expected_npz_count};"
                f"force_derivation_input_ready={force_derivation_input_ready};"
                f"delta_force_derivation_validation_ready={force_validation_ready}"
            ),
            "delta_force labels or a validated -grad(delta_energy) derivation/evaluation set are available",
            f"{supervised_dataset_path};{validation_path};{force_artifact_recovery_work_order_path};{force_trajectory_regeneration_queue_path};{force_trajectory_regeneration_execution_probe_path};{force_gpu_worker_handoff_path};{force_gpu_worker_return_receipt_path}",
            (
                force_gpu_worker_return_receipt_next_required_step
                if force_gpu_worker_handoff_ready and not force_gpu_worker_return_receipt_ready
                else force_gpu_worker_handoff_next_required_step
                if force_gpu_worker_handoff_ready
                else "Provision a compatible GPU backend or run the trajectory regeneration pilot on a GPU-equipped worker, then rerun the execution probe."
                if force_trajectory_regeneration_queue_execution_ready
                and not force_trajectory_regeneration_engine_runtime_ready
                else
                "Run the residual force trajectory regeneration queue command, then rerun residual_force_derivation_validation."
                if force_trajectory_regeneration_queue_execution_ready and not force_validation_ready
                else force_artifact_recovery_next_required_step
            )
            if force_artifact_recovery_required
            else force_derivation_next_required_step
            or "Create force labels or validate a force derivation path from energy gradients with shape, unit, and physics guard checks.",
        ),
        _work_row(
            "energy_force_dataset_materialization",
            "pass" if ready else "fail",
            f"label_fields={','.join(label_fields)};missing_production_output_labels={','.join(missing_labels)}",
            "supervised dataset or attached validation evidence can satisfy delta_energy and delta_force production output heads",
            supervised_dataset_path,
            "Materialize delta_energy/delta_force labels or attach validated proxy evidence, then rebuild the supervised dataset and training-data contract.",
        ),
    ]

    summary = {
        "packet_type": "residual_energy_force_label_evidence_work_order",
        "status": "residual_energy_force_label_evidence_ready" if ready else "blocked_residual_energy_force_label_evidence",
        "energy_force_label_evidence_ready": ready,
        "delta_energy_label_evidence_ready": delta_energy_evidence_ready,
        "delta_force_label_evidence_ready": delta_force_evidence_ready,
        "energy_proxy_candidate_ready": energy_proxy_candidate_ready,
        "stage3_energy_proxy_candidate_ready": stage3_energy_proxy_candidate_ready,
        "embedded_energy_proxy_candidate_ready": embedded_energy_proxy_candidate_ready,
        "validation_joined_energy_proxy_pair_count": validation_joined_energy_proxy_pair_count,
        "validation_stage3_energy_proxy_pair_count": validation_stage3_energy_proxy_pair_count,
        "validation_embedded_delta_energy_proxy_pair_count": validation_embedded_delta_energy_proxy_pair_count,
        "validation_energy_proxy_source_mode": validation_energy_proxy_source_mode,
        "delta_energy_proxy_validation_ready": energy_validation_ready,
        "delta_force_derivation_validation_ready": force_validation_ready,
        "force_derivation_input_ready": force_derivation_input_ready,
        "force_derivation_valid_trajectory_path_rows": force_derivation_valid_trajectory_path_rows,
        "force_derivation_existing_trajectory_npz_rows": force_derivation_existing_trajectory_npz_rows,
        "force_derivation_input_sample_count": force_derivation_input_sample_count,
        "force_derivation_effective_min_existing_npz_rows": force_derivation_effective_min_existing_npz_rows,
        "force_derivation_existing_npz_floor_capped_by_available_paths": force_derivation_existing_npz_floor_capped,
        "force_derivation_next_required_step": force_derivation_next_required_step,
        "force_artifact_recovery_work_order_artifact": force_artifact_recovery_work_order_path,
        "force_artifact_recovery_required": force_artifact_recovery_required,
        "force_artifact_missing_trajectory_npz_rows": force_artifact_missing_trajectory_npz_rows,
        "force_artifact_top_missing_prefix": force_artifact_top_missing_prefix,
        "force_artifact_top_missing_source": force_artifact_top_missing_source,
        "force_artifact_recovery_next_required_step": force_artifact_recovery_next_required_step,
        "force_trajectory_regeneration_queue_artifact": force_trajectory_regeneration_queue_path,
        "force_trajectory_regeneration_queue_ready": force_trajectory_regeneration_queue_ready,
        "force_trajectory_regeneration_queue_execution_ready": force_trajectory_regeneration_queue_execution_ready,
        "force_trajectory_regeneration_queue_rows": force_trajectory_regeneration_queue_rows,
        "force_trajectory_regeneration_queue_command": force_trajectory_regeneration_queue_command,
        "force_trajectory_regeneration_execution_probe_artifact": force_trajectory_regeneration_execution_probe_path,
        "force_trajectory_regeneration_engine_runtime_ready": force_trajectory_regeneration_engine_runtime_ready,
        "force_trajectory_regeneration_gpu_backend_unavailable": force_trajectory_regeneration_gpu_backend_unavailable,
        "force_trajectory_regeneration_pilot_abort_reason": force_trajectory_regeneration_pilot_abort_reason,
        "force_gpu_worker_handoff_artifact": force_gpu_worker_handoff_path,
        "force_gpu_worker_handoff_ready": force_gpu_worker_handoff_ready,
        "force_gpu_worker_handoff_required": force_gpu_worker_handoff_required,
        "force_gpu_worker_handoff_next_required_step": force_gpu_worker_handoff_next_required_step,
        "force_gpu_worker_return_receipt_artifact": force_gpu_worker_return_receipt_path,
        "force_gpu_worker_return_receipt_ready": force_gpu_worker_return_receipt_ready,
        "force_gpu_worker_return_receipt_blockers": force_gpu_worker_return_receipt_blockers,
        "force_gpu_worker_return_summary_manifest_bound": (
            force_gpu_worker_return_summary_manifest_bound
        ),
        "force_gpu_worker_return_summary_manifest_csv": force_gpu_worker_return_summary_manifest_csv,
        "force_gpu_worker_return_summary_out_manifest_csv_present": (
            force_gpu_worker_return_summary_out_manifest_csv_present
        ),
        "force_gpu_worker_return_summary_out_manifest_csv": force_gpu_worker_return_summary_out_manifest_csv,
        "force_gpu_worker_return_summary_out_manifest_csv_bound": (
            force_gpu_worker_return_summary_out_manifest_csv_bound
        ),
        "force_gpu_worker_return_summary_out_summary_json_bound": (
            force_gpu_worker_return_summary_out_summary_json_bound
        ),
        "force_gpu_worker_return_summary_out_summary_json": force_gpu_worker_return_summary_out_summary_json,
        "force_gpu_worker_return_summary_manifest_row_counts_consistent": (
            force_gpu_worker_return_summary_manifest_row_counts_consistent
        ),
        "force_gpu_worker_return_receipt_next_required_step": force_gpu_worker_return_receipt_next_required_step,
        "force_gpu_worker_return_summary_ok_rows": int(force_gpu_return_receipt.get("summary_ok_rows") or 0),
        "force_gpu_worker_return_manifest_ok_row_count": int(
            force_gpu_return_receipt.get("manifest_ok_row_count") or 0
        ),
        "force_gpu_worker_return_manifest_status_placeholder_count": (
            force_gpu_worker_return_manifest_status_placeholder_count
        ),
        "force_gpu_worker_return_manifest_status_invalid_count": force_gpu_worker_return_manifest_status_invalid_count,
        "force_gpu_worker_return_manifest_allowed_ok_status_values": (
            force_gpu_worker_return_manifest_allowed_ok_status_values
        ),
        "force_gpu_worker_return_manifest_npz_paths_complete": (
            force_gpu_worker_return_manifest_npz_paths_complete
        ),
        "force_gpu_worker_return_manifest_npz_path_present_count": (
            force_gpu_worker_return_manifest_npz_path_present_count
        ),
        "force_gpu_worker_return_manifest_npz_path_missing_count": (
            force_gpu_worker_return_manifest_npz_path_missing_count
        ),
        "force_gpu_worker_return_manifest_ok_row_missing_npz_path_count": (
            force_gpu_worker_return_manifest_ok_row_missing_npz_path_count
        ),
        "force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count": (
            force_gpu_worker_return_manifest_operator_verified_missing_npz_path_count
        ),
        "force_gpu_worker_return_manifest_npz_files_exist": force_gpu_worker_return_manifest_npz_files_exist,
        "force_gpu_worker_return_manifest_npz_file_existing_count": (
            force_gpu_worker_return_manifest_npz_file_existing_count
        ),
        "force_gpu_worker_return_manifest_npz_file_missing_count": (
            force_gpu_worker_return_manifest_npz_file_missing_count
        ),
        "force_gpu_worker_return_manifest_ok_row_missing_npz_file_count": (
            force_gpu_worker_return_manifest_ok_row_missing_npz_file_count
        ),
        "force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count": (
            force_gpu_worker_return_manifest_operator_verified_missing_npz_file_count
        ),
        "force_gpu_worker_return_manifest_npz_files_valid": force_gpu_worker_return_manifest_npz_files_valid,
        "force_gpu_worker_return_manifest_npz_file_valid_count": (
            force_gpu_worker_return_manifest_npz_file_valid_count
        ),
        "force_gpu_worker_return_manifest_npz_file_invalid_count": (
            force_gpu_worker_return_manifest_npz_file_invalid_count
        ),
        "force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count": (
            force_gpu_worker_return_manifest_ok_row_invalid_npz_file_count
        ),
        "force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count": (
            force_gpu_worker_return_manifest_operator_verified_invalid_npz_file_count
        ),
        "force_gpu_worker_return_manifest_npz_schema_valid": force_gpu_worker_return_manifest_npz_schema_valid,
        "force_gpu_worker_return_manifest_npz_schema_valid_count": (
            force_gpu_worker_return_manifest_npz_schema_valid_count
        ),
        "force_gpu_worker_return_manifest_npz_schema_invalid_count": (
            force_gpu_worker_return_manifest_npz_schema_invalid_count
        ),
        "force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count": (
            force_gpu_worker_return_manifest_ok_row_invalid_npz_schema_count
        ),
        "force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count": (
            force_gpu_worker_return_manifest_operator_verified_invalid_npz_schema_count
        ),
        "force_gpu_worker_return_manifest_npz_identity_valid": force_gpu_worker_return_manifest_npz_identity_valid,
        "force_gpu_worker_return_manifest_npz_identity_valid_count": (
            force_gpu_worker_return_manifest_npz_identity_valid_count
        ),
        "force_gpu_worker_return_manifest_npz_identity_invalid_count": (
            force_gpu_worker_return_manifest_npz_identity_invalid_count
        ),
        "force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count": (
            force_gpu_worker_return_manifest_ok_row_invalid_npz_identity_count
        ),
        "force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count": (
            force_gpu_worker_return_manifest_operator_verified_invalid_npz_identity_count
        ),
        "force_gpu_worker_return_identity_coverage_ready": force_gpu_worker_return_identity_coverage_ready,
        "force_gpu_worker_return_matched_queue_id_count": force_gpu_worker_return_matched_queue_id_count,
        "force_gpu_worker_return_matched_expected_npz_count": force_gpu_worker_return_matched_expected_npz_count,
        "force_gpu_worker_return_missing_queue_id_count": force_gpu_worker_return_missing_queue_id_count,
        "force_gpu_worker_return_missing_expected_npz_count": force_gpu_worker_return_missing_expected_npz_count,
        "pdbbind_pose_affinity_preflight_ready": pdbbind_preflight_ready,
        "validation_blockers": validation_blockers,
        "validation_artifact": validation_path,
        "supervised_rows": len(supervised_rows),
        "supervised_key_count": len(supervised_keys),
        "stage3_candidate_source_count": len(stage3_paths),
        "scanned_stage3_source_count": len(source_rows),
        "joined_supervised_rows": joined_rows,
        "energy_proxy_rows": energy_proxy_rows,
        "unique_energy_proxy_keys": energy_proxy_key_count,
        "force_label_rows": force_label_rows,
        "unique_force_label_keys": force_label_key_count,
        "trajectory_npz_rows": trajectory_npz_rows,
        "backmapped_pdb_rows": backmapped_pdb_rows,
        "missing_production_output_labels": missing_labels,
        "label_fields": label_fields,
        "source_artifacts": [
            supervised_dataset_path,
            validation_path,
            pdbbind_preflight_path,
            force_artifact_recovery_work_order_path,
            force_trajectory_regeneration_queue_path,
            force_trajectory_regeneration_execution_probe_path,
            force_gpu_worker_handoff_path,
            force_gpu_worker_return_receipt_path,
        ],
        "execution_enabled": False,
        "label_materialized": False,
        "validation_executed": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Energy/force label evidence is ready; rebuild the training-data contract."
            if ready
            else rows[0]["next_action"]
            if rows[0]["status"] != "pass"
            else rows[1]["next_action"]
            if rows[1]["status"] != "pass"
            else rows[2]["next_action"]
        ),
    }
    public_source_rows = [
        {key: value for key, value in row.items() if not str(key).startswith("_")}
        for row in source_rows
    ]
    return {"summary": summary, "rows": rows, "sources": public_source_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Energy/Force Label Evidence Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- energy_force_label_evidence_ready: `{s['energy_force_label_evidence_ready']}`",
        f"- delta_energy_label_evidence_ready: `{s['delta_energy_label_evidence_ready']}`",
        f"- delta_force_label_evidence_ready: `{s['delta_force_label_evidence_ready']}`",
        f"- energy_proxy_rows: `{s['energy_proxy_rows']}`",
        f"- unique_energy_proxy_keys: `{s['unique_energy_proxy_keys']}`",
        f"- joined_supervised_rows: `{s['joined_supervised_rows']}`",
        f"- force_label_rows: `{s['force_label_rows']}`",
        f"- unique_force_label_keys: `{s['unique_force_label_keys']}`",
        f"- trajectory_npz_rows: `{s['trajectory_npz_rows']}`",
        f"- backmapped_pdb_rows: `{s['backmapped_pdb_rows']}`",
        f"- force_artifact_recovery_required: `{s['force_artifact_recovery_required']}`",
        f"- force_artifact_missing_trajectory_npz_rows: `{s['force_artifact_missing_trajectory_npz_rows']}`",
        f"- force_artifact_top_missing_prefix: `{s['force_artifact_top_missing_prefix']}`",
        f"- force_artifact_top_missing_source: `{s['force_artifact_top_missing_source']}`",
        f"- force_trajectory_regeneration_queue_execution_ready: `{s['force_trajectory_regeneration_queue_execution_ready']}`",
        f"- force_trajectory_regeneration_queue_rows: `{s['force_trajectory_regeneration_queue_rows']}`",
        f"- force_trajectory_regeneration_engine_runtime_ready: `{s['force_trajectory_regeneration_engine_runtime_ready']}`",
        f"- force_trajectory_regeneration_gpu_backend_unavailable: `{s['force_trajectory_regeneration_gpu_backend_unavailable']}`",
        f"- force_gpu_worker_handoff_ready: `{s['force_gpu_worker_handoff_ready']}`",
        f"- force_gpu_worker_return_receipt_ready: `{s['force_gpu_worker_return_receipt_ready']}`",
        f"- force_gpu_worker_return_receipt_blockers: `{','.join(s['force_gpu_worker_return_receipt_blockers'])}`",
        f"- force_gpu_worker_return_summary_manifest_bound: `{s['force_gpu_worker_return_summary_manifest_bound']}`",
        f"- force_gpu_worker_return_summary_manifest_csv: `{s['force_gpu_worker_return_summary_manifest_csv']}`",
        f"- force_gpu_worker_return_summary_out_manifest_csv_present: `{s['force_gpu_worker_return_summary_out_manifest_csv_present']}`",
        f"- force_gpu_worker_return_summary_out_manifest_csv: `{s['force_gpu_worker_return_summary_out_manifest_csv']}`",
        f"- force_gpu_worker_return_summary_out_manifest_csv_bound: `{s['force_gpu_worker_return_summary_out_manifest_csv_bound']}`",
        f"- force_gpu_worker_return_summary_out_summary_json_bound: `{s['force_gpu_worker_return_summary_out_summary_json_bound']}`",
        f"- force_gpu_worker_return_summary_out_summary_json: `{s['force_gpu_worker_return_summary_out_summary_json']}`",
        f"- force_gpu_worker_return_summary_manifest_row_counts_consistent: `{s['force_gpu_worker_return_summary_manifest_row_counts_consistent']}`",
        f"- force_gpu_worker_return_manifest_npz_paths_complete: `{s['force_gpu_worker_return_manifest_npz_paths_complete']}`",
        f"- force_gpu_worker_return_manifest_npz_path_present_count: `{s['force_gpu_worker_return_manifest_npz_path_present_count']}`",
        f"- force_gpu_worker_return_manifest_npz_files_exist: `{s['force_gpu_worker_return_manifest_npz_files_exist']}`",
        f"- force_gpu_worker_return_manifest_npz_file_existing_count: `{s['force_gpu_worker_return_manifest_npz_file_existing_count']}`",
        f"- force_gpu_worker_return_manifest_npz_files_valid: `{s['force_gpu_worker_return_manifest_npz_files_valid']}`",
        f"- force_gpu_worker_return_manifest_npz_file_valid_count: `{s['force_gpu_worker_return_manifest_npz_file_valid_count']}`",
        f"- force_gpu_worker_return_manifest_npz_schema_valid: `{s['force_gpu_worker_return_manifest_npz_schema_valid']}`",
        f"- force_gpu_worker_return_manifest_npz_schema_valid_count: `{s['force_gpu_worker_return_manifest_npz_schema_valid_count']}`",
        f"- force_gpu_worker_return_manifest_npz_identity_valid: `{s['force_gpu_worker_return_manifest_npz_identity_valid']}`",
        f"- force_gpu_worker_return_manifest_npz_identity_valid_count: `{s['force_gpu_worker_return_manifest_npz_identity_valid_count']}`",
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
    lines.extend(
        [
            "",
            "## Source Files",
            "",
            "| source | status | joined | energy proxy rows | force rows |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in payload["sources"][:24]:
        lines.append(
            f"| `{row['source_csv']}` | `{row['status']}` | `{row['joined_supervised_rows']}` | `{row['energy_proxy_rows']}` | `{row['force_label_rows']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual energy/force label evidence work order.")
    parser.add_argument("--supervised-dataset-json", default=DEFAULT_SUPERVISED_DATASET_JSON)
    parser.add_argument("--validation-json", default=DEFAULT_VALIDATION_JSON)
    parser.add_argument("--pdbbind-preflight-json", default=DEFAULT_PDBBIND_PREFLIGHT_JSON)
    parser.add_argument("--force-artifact-recovery-work-order-json", default=DEFAULT_FORCE_ARTIFACT_RECOVERY_WORK_ORDER_JSON)
    parser.add_argument("--force-trajectory-regeneration-queue-json", default=DEFAULT_FORCE_TRAJECTORY_REGENERATION_QUEUE_JSON)
    parser.add_argument(
        "--force-trajectory-regeneration-execution-probe-json",
        default=DEFAULT_FORCE_TRAJECTORY_REGENERATION_EXECUTION_PROBE_JSON,
    )
    parser.add_argument("--force-gpu-worker-handoff-json", default=DEFAULT_FORCE_GPU_WORKER_HANDOFF_JSON)
    parser.add_argument("--force-gpu-worker-return-receipt-json", default=DEFAULT_FORCE_GPU_WORKER_RETURN_RECEIPT_JSON)
    parser.add_argument("--min-energy-proxy-rows", type=int, default=1000)
    parser.add_argument("--max-sources", type=int, default=24)
    parser.add_argument("--max-rows-per-source", type=int, default=20000)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_energy_force_label_evidence_work_order(
        supervised_dataset_packet=_read_json_if_present(args.supervised_dataset_json),
        validation_packet=_read_json_if_present(args.validation_json),
        pdbbind_preflight_packet=_read_json_if_present(args.pdbbind_preflight_json),
        force_artifact_recovery_work_order_packet=_read_json_if_present(args.force_artifact_recovery_work_order_json),
        force_trajectory_regeneration_queue_packet=_read_json_if_present(args.force_trajectory_regeneration_queue_json),
        force_trajectory_regeneration_execution_probe_packet=_read_json_if_present(
            args.force_trajectory_regeneration_execution_probe_json
        ),
        force_gpu_worker_handoff_packet=_read_json_if_present(args.force_gpu_worker_handoff_json),
        force_gpu_worker_return_receipt_packet=_read_json_if_present(args.force_gpu_worker_return_receipt_json),
        supervised_dataset_path=args.supervised_dataset_json,
        validation_path=args.validation_json,
        pdbbind_preflight_path=args.pdbbind_preflight_json,
        force_artifact_recovery_work_order_path=args.force_artifact_recovery_work_order_json,
        force_trajectory_regeneration_queue_path=args.force_trajectory_regeneration_queue_json,
        force_trajectory_regeneration_execution_probe_path=args.force_trajectory_regeneration_execution_probe_json,
        force_gpu_worker_handoff_path=args.force_gpu_worker_handoff_json,
        force_gpu_worker_return_receipt_path=args.force_gpu_worker_return_receipt_json,
        min_energy_proxy_rows=args.min_energy_proxy_rows,
        max_sources=args.max_sources,
        max_rows_per_source=args.max_rows_per_source,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
