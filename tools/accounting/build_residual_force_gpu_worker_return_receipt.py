#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_REGENERATION_QUEUE_JSON = "runs/residual_force_trajectory_regeneration_queue_current.json"
DEFAULT_REGENERATION_SUMMARY_JSON = "runs/residual_force_trajectory_regeneration_current_summary.json"
DEFAULT_REGENERATION_MANIFEST_CSV = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
DEFAULT_DERIVATION_VALIDATION_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_return_receipt_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_return_receipt_current.md"

CLAIM_BOUNDARY = (
    "Residual force GPU worker return receipt only; verifies returned full-regeneration summary/manifest artifacts "
    "and post-run force-derivation validation evidence. It does not run docking, regenerate trajectories, derive "
    "force labels, train models, create checkpoints, promote production mode, upload, submit, email, delete, or "
    "mutate external state."
)

REQUIRED_HANDOFF_VALIDATION_MARKERS = (
    "build_residual_force_gpu_worker_return_receipt.py",
    "build_residual_force_derivation_validation.py",
    "build_residual_energy_force_label_validation.py",
    "build_residual_energy_force_label_evidence_work_order.py",
    "build_residual_uncertainty_policy_evidence_contract.py",
    "build_residual_production_training_data_contract.py",
    "train_residual_production_score_model.py",
    "build_residual_production_checkpoint_sidecar.py",
    "build_residual_production_checkpoint_preflight.py",
    "build_residual_production_checkpoint_work_order.py",
    "build_residual_model_registry.py",
    "build_product_ai_architecture_execution_backlog.py",
    "build_product_ai_architecture_gap_closure.py",
    "build_product_goal_completion_audit.py",
)
REQUIRED_HANDOFF_PROMOTION_LADDER_READY_KEYS = (
    "gpu_worker_return_receipt_ready",
    "delta_force_derivation_validation_ready",
    "delta_force_label_evidence_ready",
    "production_training_data_ready",
    "score_model_production_checkpoint_ready",
    "sidecar_ready",
    "checkpoint_preflight_ready",
    "production_promotion_allowed",
    "all_gaps_closed",
    "goal_complete",
)
REQUIRED_PRODUCTION_OUTPUT_FIELDS = (
    "delta_score",
    "corrected_score",
    "delta_energy",
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)
REQUIRED_GPU_RETURN_UNLOCK_OUTPUT_FIELDS = (
    "delta_force",
    "uncertainty",
    "abstention_reason",
    "stage2_route_decision",
)
PRODUCTION_GPU_BACKEND_PREFIXES = ("rust_hip",)
NON_PRODUCTION_BACKEND_MARKERS = ("cpu", "pytorch")

MANIFEST_OK_STATUS_VALUES = {"ok", "ok_npz_bundle", "ok_regenerated_npz", "ok_full_regeneration"}
MANIFEST_FAILED_STATUS_VALUES = {"failed", "error", "missing", "aborted", "skipped"}
MANIFEST_STATUS_PLACEHOLDER_VALUES = {"", "operator_fill_ok_or_failed"}

OPERATOR_VERIFICATION_COLUMN = "operator_verified_npz_exists"
OPERATOR_VERIFICATION_TRUTHY_VALUES = {"true", "yes", "1", "ok", "verified"}
OPERATOR_VERIFICATION_FALSEY_VALUES = {"false", "no", "0", "missing", "failed", "not_found"}
OPERATOR_VERIFICATION_PLACEHOLDER_VALUES = {"", "operator_fill_true_or_false"}
MANIFEST_NPZ_PATH_COLUMNS = (
    "expected_regenerated_trajectory_npz",
    "trajectory_npz",
    "output_npz",
    "generated_npz",
)
REQUIRED_NPZ_SCHEMA_KEYS = ("protein_ca", "ligand_frames")
REQUIRED_NPZ_IDENTITY_KEYS = ("queue_id",)


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


def _bool(value: Any) -> bool:
    return value is True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _summary_manifest_csv(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    return _text(
        summary.get("out_manifest_csv")
        or summary.get("manifest_csv")
        or artifacts.get("manifest_csv")
    )


def _summary_out_manifest_csv(summary: dict[str, Any]) -> str:
    return _text(summary.get("out_manifest_csv"))


def _summary_out_summary_json(summary: dict[str, Any]) -> str:
    return _text(summary.get("out_summary_json"))


def _same_resolved_path(left: str, right: str) -> bool:
    if not _text(left) or not _text(right):
        return False
    try:
        return _resolve(left).resolve() == _resolve(right).resolve()
    except OSError:
        return _resolve(left) == _resolve(right)


def _handoff_promotion_ladder_status(handoff: dict[str, Any]) -> dict[str, Any]:
    ladder = handoff.get("post_return_promotion_ladder")
    rows = [row for row in ladder if isinstance(row, dict)] if isinstance(ladder, list) else []
    ready_keys = {_text(row.get("ready_key")) for row in rows}
    missing_ready_keys = [
        ready_key for ready_key in REQUIRED_HANDOFF_PROMOTION_LADDER_READY_KEYS if ready_key not in ready_keys
    ]
    ready = bool(
        handoff.get("post_return_promotion_ladder_ready") is True
        and not missing_ready_keys
        and len(rows) >= len(REQUIRED_HANDOFF_PROMOTION_LADDER_READY_KEYS)
    )
    return {
        "ready": ready,
        "stage_count": len(rows),
        "missing_ready_keys": missing_ready_keys,
    }


def _csv_rows(path_like: str | Path) -> tuple[bool, list[dict[str, str]], bool]:
    path = _resolve(path_like)
    if not path.exists():
        return False, [], False
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            return True, [dict(row) for row in csv.DictReader(fh)], False
    except OSError:
        return True, [], True


def _manifest_npz_path(row: dict[str, Any]) -> str:
    for column in MANIFEST_NPZ_PATH_COLUMNS:
        value = _text(row.get(column))
        if value:
            return value
    return ""


def _npz_path_exists(npz_path: str, *, manifest_csv_path: Path) -> bool:
    path = Path(npz_path)
    candidates = [path] if path.is_absolute() else [ROOT / path, manifest_csv_path.parent / path]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return True
        except OSError:
            continue
    return False


def _npz_existing_candidate(npz_path: str, *, manifest_csv_path: Path) -> Path | None:
    path = Path(npz_path)
    candidates = [path] if path.is_absolute() else [ROOT / path, manifest_csv_path.parent / path]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _npz_path_valid(npz_path: str, *, manifest_csv_path: Path) -> bool:
    path = Path(npz_path)
    candidates = [path] if path.is_absolute() else [ROOT / path, manifest_csv_path.parent / path]
    for candidate in candidates:
        try:
            if not candidate.is_file() or candidate.stat().st_size <= 0:
                continue
            if not zipfile.is_zipfile(candidate):
                continue
            with zipfile.ZipFile(candidate) as zf:
                if zf.namelist():
                    return True
        except (OSError, zipfile.BadZipFile):
            continue
    return False


def _npz_path_schema_valid(npz_path: str, *, manifest_csv_path: Path) -> bool:
    path = Path(npz_path)
    candidates = [path] if path.is_absolute() else [ROOT / path, manifest_csv_path.parent / path]
    for candidate in candidates:
        try:
            if not candidate.is_file() or candidate.stat().st_size <= 0 or not zipfile.is_zipfile(candidate):
                continue
            with np.load(candidate, allow_pickle=False) as data:
                if any(key not in data.files for key in REQUIRED_NPZ_SCHEMA_KEYS):
                    continue
                protein_ca = np.asarray(data["protein_ca"])
                ligand_frames = np.asarray(data["ligand_frames"])
                frame_indices = np.asarray(data["frame_indices"]) if "frame_indices" in data.files else None
                protein_ca_ok = bool(
                    protein_ca.ndim == 2
                    and protein_ca.shape[0] > 0
                    and protein_ca.shape[1] == 3
                    and np.isfinite(protein_ca).all()
                )
                ligand_frames_ok = bool(
                    ligand_frames.ndim == 3
                    and ligand_frames.shape[0] > 0
                    and ligand_frames.shape[1] > 0
                    and ligand_frames.shape[2] == 3
                    and np.isfinite(ligand_frames).all()
                )
                frame_indices_ok = bool(
                    frame_indices is None
                    or (
                        frame_indices.ndim == 1
                        and frame_indices.shape[0] == ligand_frames.shape[0]
                        and np.isfinite(frame_indices).all()
                    )
                )
                if protein_ca_ok and ligand_frames_ok and frame_indices_ok:
                    return True
        except (OSError, ValueError, zipfile.BadZipFile):
            continue
    return False


def _npz_scalar_text(data: Any, key: str) -> str:
    if key not in data.files:
        return ""
    try:
        value = np.asarray(data[key])
        if value.shape == ():
            return str(value.item()).strip()
        if value.size == 1:
            return str(value.reshape(-1)[0].item()).strip()
    except (OSError, ValueError, TypeError):
        return ""
    return ""


def _npz_identity_matches(
    npz_path: str,
    *,
    manifest_csv_path: Path,
    expected: dict[str, str],
) -> bool:
    candidate = _npz_existing_candidate(npz_path, manifest_csv_path=manifest_csv_path)
    if candidate is None:
        return False
    try:
        with np.load(candidate, allow_pickle=False) as data:
            for key in REQUIRED_NPZ_IDENTITY_KEYS:
                if not _text(expected.get(key)) or _npz_scalar_text(data, key) != _text(expected.get(key)):
                    return False
            for key in ("target", "ligand_id"):
                expected_value = _text(expected.get(key))
                if expected_value and _npz_scalar_text(data, key) != expected_value:
                    return False
            return True
    except (OSError, ValueError, zipfile.BadZipFile):
        return False


def _manifest_counts(path_like: str | Path) -> dict[str, Any]:
    manifest_csv_path = _resolve(path_like)
    present, rows, read_error = _csv_rows(path_like)
    if not present:
        return {
            "manifest_present": False,
            "manifest_row_count": 0,
            "manifest_ok_row_count": 0,
            "manifest_failed_row_count": 0,
            "manifest_status_placeholder_count": 0,
            "manifest_status_invalid_count": 0,
            "manifest_status_values": "",
            "manifest_operator_verification_column_present": False,
            "manifest_operator_verified_true_count": 0,
            "manifest_operator_verification_placeholder_count": 0,
            "manifest_operator_verification_false_count": 0,
            "manifest_operator_verification_invalid_count": 0,
            "manifest_npz_path_column_present": False,
            "manifest_npz_path_present_count": 0,
            "manifest_npz_path_missing_count": 0,
            "manifest_ok_row_missing_npz_path_count": 0,
            "manifest_operator_verified_missing_npz_path_count": 0,
            "manifest_npz_file_existing_count": 0,
            "manifest_npz_file_missing_count": 0,
            "manifest_ok_row_missing_npz_file_count": 0,
            "manifest_operator_verified_missing_npz_file_count": 0,
            "manifest_npz_file_valid_count": 0,
            "manifest_npz_file_invalid_count": 0,
            "manifest_ok_row_invalid_npz_file_count": 0,
            "manifest_operator_verified_invalid_npz_file_count": 0,
            "manifest_npz_schema_valid_count": 0,
            "manifest_npz_schema_invalid_count": 0,
            "manifest_ok_row_invalid_npz_schema_count": 0,
            "manifest_operator_verified_invalid_npz_schema_count": 0,
        }
    row_count = 0
    ok_count = 0
    failed_count = 0
    status_placeholder_count = 0
    status_invalid_count = 0
    operator_verified_true_count = 0
    operator_verification_placeholder_count = 0
    operator_verification_false_count = 0
    operator_verification_invalid_count = 0
    operator_verification_column_present = any(OPERATOR_VERIFICATION_COLUMN in row for row in rows)
    npz_path_column_present = any(any(column in row for column in MANIFEST_NPZ_PATH_COLUMNS) for row in rows)
    npz_path_present_count = 0
    npz_path_missing_count = 0
    ok_row_missing_npz_path_count = 0
    operator_verified_missing_npz_path_count = 0
    npz_file_existing_count = 0
    npz_file_missing_count = 0
    ok_row_missing_npz_file_count = 0
    operator_verified_missing_npz_file_count = 0
    npz_file_valid_count = 0
    npz_file_invalid_count = 0
    ok_row_invalid_npz_file_count = 0
    operator_verified_invalid_npz_file_count = 0
    npz_schema_valid_count = 0
    npz_schema_invalid_count = 0
    ok_row_invalid_npz_schema_count = 0
    operator_verified_invalid_npz_schema_count = 0
    statuses: set[str] = set()
    for row in rows:
        row_count += 1
        status = _text(row.get("status"))
        status_normalized = status.lower()
        npz_path = _manifest_npz_path(row)
        if npz_path:
            npz_path_present_count += 1
            npz_file_exists = _npz_path_exists(npz_path, manifest_csv_path=manifest_csv_path)
            if npz_file_exists:
                npz_file_existing_count += 1
                npz_file_valid = _npz_path_valid(npz_path, manifest_csv_path=manifest_csv_path)
                if npz_file_valid:
                    npz_file_valid_count += 1
                    npz_schema_valid = _npz_path_schema_valid(npz_path, manifest_csv_path=manifest_csv_path)
                    if npz_schema_valid:
                        npz_schema_valid_count += 1
                    else:
                        npz_schema_invalid_count += 1
                else:
                    npz_file_invalid_count += 1
                    npz_schema_valid = False
            else:
                npz_file_missing_count += 1
                npz_file_valid = False
                npz_schema_valid = False
        else:
            npz_path_missing_count += 1
            npz_file_exists = False
            npz_file_valid = False
            npz_schema_valid = False
        if status:
            statuses.add(status)
        if status_normalized in MANIFEST_OK_STATUS_VALUES:
            ok_count += 1
            if not npz_path:
                ok_row_missing_npz_path_count += 1
            elif not npz_file_exists:
                ok_row_missing_npz_file_count += 1
            elif not npz_file_valid:
                ok_row_invalid_npz_file_count += 1
            elif not npz_schema_valid:
                ok_row_invalid_npz_schema_count += 1
        elif status_normalized in MANIFEST_STATUS_PLACEHOLDER_VALUES or status_normalized.startswith("operator_fill"):
            status_placeholder_count += 1
        elif status_normalized in MANIFEST_FAILED_STATUS_VALUES:
            failed_count += 1
        else:
            status_invalid_count += 1
        operator_verified = _text(row.get(OPERATOR_VERIFICATION_COLUMN)).lower()
        if operator_verified in OPERATOR_VERIFICATION_TRUTHY_VALUES:
            operator_verified_true_count += 1
            if not npz_path:
                operator_verified_missing_npz_path_count += 1
            elif not npz_file_exists:
                operator_verified_missing_npz_file_count += 1
            elif not npz_file_valid:
                operator_verified_invalid_npz_file_count += 1
            elif not npz_schema_valid:
                operator_verified_invalid_npz_schema_count += 1
        elif operator_verified in OPERATOR_VERIFICATION_PLACEHOLDER_VALUES or operator_verified.startswith("operator_fill"):
            operator_verification_placeholder_count += 1
        elif operator_verified in OPERATOR_VERIFICATION_FALSEY_VALUES:
            operator_verification_false_count += 1
        else:
            operator_verification_invalid_count += 1
    return {
        "manifest_present": True,
        "manifest_row_count": row_count,
        "manifest_ok_row_count": ok_count,
        "manifest_failed_row_count": failed_count,
        "manifest_status_placeholder_count": status_placeholder_count,
        "manifest_status_invalid_count": status_invalid_count,
        "manifest_status_values": ",".join(sorted(statuses)[:12]),
        "manifest_read_error": read_error,
        "manifest_operator_verification_column_present": operator_verification_column_present,
        "manifest_operator_verified_true_count": operator_verified_true_count,
        "manifest_operator_verification_placeholder_count": operator_verification_placeholder_count,
        "manifest_operator_verification_false_count": operator_verification_false_count,
        "manifest_operator_verification_invalid_count": operator_verification_invalid_count,
        "manifest_npz_path_column_present": npz_path_column_present,
        "manifest_npz_path_present_count": npz_path_present_count,
        "manifest_npz_path_missing_count": npz_path_missing_count,
        "manifest_ok_row_missing_npz_path_count": ok_row_missing_npz_path_count,
        "manifest_operator_verified_missing_npz_path_count": operator_verified_missing_npz_path_count,
        "manifest_npz_file_existing_count": npz_file_existing_count,
        "manifest_npz_file_missing_count": npz_file_missing_count,
        "manifest_ok_row_missing_npz_file_count": ok_row_missing_npz_file_count,
        "manifest_operator_verified_missing_npz_file_count": operator_verified_missing_npz_file_count,
        "manifest_npz_file_valid_count": npz_file_valid_count,
        "manifest_npz_file_invalid_count": npz_file_invalid_count,
        "manifest_ok_row_invalid_npz_file_count": ok_row_invalid_npz_file_count,
        "manifest_operator_verified_invalid_npz_file_count": operator_verified_invalid_npz_file_count,
        "manifest_npz_schema_valid_count": npz_schema_valid_count,
        "manifest_npz_schema_invalid_count": npz_schema_invalid_count,
        "manifest_ok_row_invalid_npz_schema_count": ok_row_invalid_npz_schema_count,
        "manifest_operator_verified_invalid_npz_schema_count": operator_verified_invalid_npz_schema_count,
    }


def _queue_rows_from_packet_or_csv(packet: dict[str, Any], queue_packet_path: str) -> tuple[bool, list[dict[str, str]], bool]:
    summary = _summary(packet)
    csv_path = _text(summary.get("regeneration_queue_csv"))
    if csv_path:
        csv_present, csv_rows, csv_read_error = _csv_rows(csv_path)
        if csv_present:
            return csv_present, csv_rows, csv_read_error
    rows = [dict(row) for row in packet.get("rows", []) or [] if isinstance(row, dict)]
    if rows:
        return True, [{str(key): _text(value) for key, value in row.items()} for row in rows], False
    csv_present, csv_rows, csv_read_error = _csv_rows(str(queue_packet_path).replace(".json", ".csv"))
    if csv_present:
        return csv_present, csv_rows, csv_read_error
    return False, [], False


def _queue_row_fingerprint(row: dict[str, str]) -> str:
    queue_id = _text(row.get("queue_id"))
    expected_npz = _text(row.get("expected_regenerated_trajectory_npz"))
    if not queue_id and not expected_npz:
        return ""
    payload = {
        "queue_id": queue_id,
        "expected_regenerated_trajectory_npz": expected_npz,
        "target": _text(row.get("target")),
        "ligand_id": _text(row.get("ligand_id")),
        "replica_idx": _text(row.get("replica_idx")),
        "simulation_seed": _text(row.get("simulation_seed")),
        "native_pdb_path": _text(row.get("native_pdb_path")),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _manifest_identity_coverage(
    *,
    queue_packet: dict[str, Any],
    queue_packet_path: str,
    manifest_csv: str,
) -> dict[str, Any]:
    queue_present, queue_rows, queue_read_error = _queue_rows_from_packet_or_csv(queue_packet, queue_packet_path)
    manifest_present, manifest_rows, manifest_read_error = _csv_rows(manifest_csv)
    queue_ids = {_text(row.get("queue_id")) for row in queue_rows if _text(row.get("queue_id"))}
    expected_npz = {_text(row.get("expected_regenerated_trajectory_npz")) for row in queue_rows if _text(row.get("expected_regenerated_trajectory_npz"))}
    queue_fingerprints = {_queue_row_fingerprint(row) for row in queue_rows if _queue_row_fingerprint(row)}
    manifest_ids = {
        _text(row.get("queue_id") or row.get("source_queue_id") or row.get("regeneration_queue_id"))
        for row in manifest_rows
        if _text(row.get("queue_id") or row.get("source_queue_id") or row.get("regeneration_queue_id"))
    }
    manifest_npz = {_manifest_npz_path(row) for row in manifest_rows if _manifest_npz_path(row)}
    manifest_fingerprints = {
        _text(row.get("queue_row_fingerprint") or row.get("source_queue_row_fingerprint"))
        for row in manifest_rows
        if _text(row.get("queue_row_fingerprint") or row.get("source_queue_row_fingerprint"))
    }
    manifest_id_values = [
        _text(row.get("queue_id") or row.get("source_queue_id") or row.get("regeneration_queue_id"))
        for row in manifest_rows
        if _text(row.get("queue_id") or row.get("source_queue_id") or row.get("regeneration_queue_id"))
    ]
    manifest_npz_values = [_manifest_npz_path(row) for row in manifest_rows if _manifest_npz_path(row)]
    manifest_fingerprint_values = [
        _text(row.get("queue_row_fingerprint") or row.get("source_queue_row_fingerprint"))
        for row in manifest_rows
        if _text(row.get("queue_row_fingerprint") or row.get("source_queue_row_fingerprint"))
    ]
    queue_by_id = {_text(row.get("queue_id")): row for row in queue_rows if _text(row.get("queue_id"))}
    queue_by_npz = {
        _text(row.get("expected_regenerated_trajectory_npz")): row
        for row in queue_rows
        if _text(row.get("expected_regenerated_trajectory_npz"))
    }
    queue_by_fingerprint = {_queue_row_fingerprint(row): row for row in queue_rows if _queue_row_fingerprint(row)}
    duplicate_id_count = len(manifest_id_values) - len(set(manifest_id_values))
    duplicate_npz_count = len(manifest_npz_values) - len(set(manifest_npz_values))
    duplicate_fingerprint_count = len(manifest_fingerprint_values) - len(set(manifest_fingerprint_values))
    duplicate_identity_count = duplicate_id_count + duplicate_npz_count + duplicate_fingerprint_count
    missing_ids = queue_ids - manifest_ids if queue_ids and manifest_ids else set()
    missing_npz = expected_npz - manifest_npz if expected_npz and manifest_npz else set()
    missing_fingerprints = queue_fingerprints - manifest_fingerprints if queue_fingerprints and manifest_fingerprints else set()
    unexpected_ids = manifest_ids - queue_ids if queue_ids and manifest_ids else set()
    unexpected_npz = manifest_npz - expected_npz if expected_npz and manifest_npz else set()
    unexpected_fingerprints = manifest_fingerprints - queue_fingerprints if queue_fingerprints and manifest_fingerprints else set()
    id_coverage_ready = bool(queue_ids and len(queue_ids & manifest_ids) >= len(queue_ids) and not missing_ids and not unexpected_ids)
    npz_coverage_ready = bool(expected_npz and len(expected_npz & manifest_npz) >= len(expected_npz) and not missing_npz and not unexpected_npz)
    fingerprint_coverage_ready = bool(
        queue_fingerprints
        and len(queue_fingerprints & manifest_fingerprints) >= len(queue_fingerprints)
        and not missing_fingerprints
        and not unexpected_fingerprints
    )
    identity_ready = bool(
        queue_present
        and manifest_present
        and not queue_read_error
        and not manifest_read_error
        and queue_rows
        and manifest_rows
        and duplicate_identity_count == 0
        and (id_coverage_ready or npz_coverage_ready or fingerprint_coverage_ready)
    )
    manifest_csv_path = _resolve(manifest_csv)
    npz_identity_valid_count = 0
    npz_identity_invalid_count = 0
    ok_row_invalid_npz_identity_count = 0
    operator_verified_invalid_npz_identity_count = 0
    for row in manifest_rows:
        npz_path = _manifest_npz_path(row)
        manifest_id = _text(row.get("queue_id") or row.get("source_queue_id") or row.get("regeneration_queue_id"))
        manifest_fingerprint = _text(row.get("queue_row_fingerprint") or row.get("source_queue_row_fingerprint"))
        matched_queue = (
            queue_by_id.get(manifest_id)
            or queue_by_npz.get(npz_path)
            or queue_by_fingerprint.get(manifest_fingerprint)
            or {}
        )
        expected_identity = {
            "queue_id": _text(matched_queue.get("queue_id") or manifest_id),
            "target": _text(matched_queue.get("target") or row.get("target")),
            "ligand_id": _text(matched_queue.get("ligand_id") or row.get("ligand_id")),
        }
        if not npz_path or not expected_identity["queue_id"]:
            identity_ok = False
        else:
            identity_ok = _npz_identity_matches(npz_path, manifest_csv_path=manifest_csv_path, expected=expected_identity)
        if identity_ok:
            npz_identity_valid_count += 1
            continue
        if npz_path:
            npz_identity_invalid_count += 1
        status_normalized = _text(row.get("status")).lower()
        operator_verified = _text(row.get(OPERATOR_VERIFICATION_COLUMN)).lower()
        if status_normalized in MANIFEST_OK_STATUS_VALUES:
            ok_row_invalid_npz_identity_count += 1
        if operator_verified in OPERATOR_VERIFICATION_TRUTHY_VALUES:
            operator_verified_invalid_npz_identity_count += 1
    return {
        "queue_present": queue_present,
        "queue_read_error": queue_read_error,
        "queue_identity_row_count": len(queue_rows),
        "queue_id_count": len(queue_ids),
        "expected_npz_count": len(expected_npz),
        "queue_fingerprint_count": len(queue_fingerprints),
        "manifest_present": manifest_present,
        "manifest_read_error": manifest_read_error,
        "manifest_identity_row_count": len(manifest_rows),
        "manifest_queue_id_count": len(manifest_ids),
        "manifest_npz_count": len(manifest_npz),
        "manifest_fingerprint_count": len(manifest_fingerprints),
        "manifest_duplicate_queue_id_count": duplicate_id_count,
        "manifest_duplicate_npz_count": duplicate_npz_count,
        "manifest_duplicate_queue_fingerprint_count": duplicate_fingerprint_count,
        "manifest_duplicate_identity_count": duplicate_identity_count,
        "manifest_matched_queue_id_count": len(queue_ids & manifest_ids),
        "manifest_matched_expected_npz_count": len(expected_npz & manifest_npz),
        "manifest_matched_queue_fingerprint_count": len(queue_fingerprints & manifest_fingerprints),
        "missing_queue_id_count": len(missing_ids),
        "missing_expected_npz_count": len(missing_npz),
        "missing_queue_fingerprint_count": len(missing_fingerprints),
        "unexpected_manifest_queue_id_count": len(unexpected_ids),
        "unexpected_manifest_npz_count": len(unexpected_npz),
        "unexpected_manifest_queue_fingerprint_count": len(unexpected_fingerprints),
        "identity_coverage_ready": identity_ready,
        "manifest_npz_identity_valid_count": npz_identity_valid_count,
        "manifest_npz_identity_invalid_count": npz_identity_invalid_count,
        "manifest_ok_row_invalid_npz_identity_count": ok_row_invalid_npz_identity_count,
        "manifest_operator_verified_invalid_npz_identity_count": operator_verified_invalid_npz_identity_count,
    }


def _row(check_id: str, status: str, observed: str, required: str, next_action: str, source_artifact: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "next_action": next_action,
        "source_artifact": source_artifact,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def _handoff_validation_chain_status(handoff: dict[str, Any]) -> dict[str, Any]:
    commands = [_text(item) for item in handoff.get("post_run_validation_commands") or [] if _text(item)]
    joined = "\n".join(commands)
    missing = [marker for marker in REQUIRED_HANDOFF_VALIDATION_MARKERS if marker not in joined]
    positions = []
    for marker in REQUIRED_HANDOFF_VALIDATION_MARKERS:
        try:
            positions.append(joined.index(marker))
        except ValueError:
            positions.append(-1)
    ordered = bool(positions and all(pos >= 0 for pos in positions) and positions == sorted(positions))
    ready = bool(commands and not missing and ordered)
    return {
        "ready": ready,
        "command_count": len(commands),
        "missing_markers": missing,
        "ordered": ordered,
    }


def _handoff_output_contract_status(handoff: dict[str, Any], expected_rows: int) -> dict[str, Any]:
    required_outputs = [_text(item) for item in handoff.get("post_return_required_production_output_fields") or []]
    unlock_outputs = [_text(item) for item in handoff.get("post_return_gpu_unlock_output_fields") or []]
    unlock_artifacts = [_text(item) for item in handoff.get("post_return_gpu_unlock_artifacts") or []]
    missing_required_outputs = [
        field for field in REQUIRED_PRODUCTION_OUTPUT_FIELDS if field not in set(required_outputs)
    ]
    missing_unlock_outputs = [
        field for field in REQUIRED_GPU_RETURN_UNLOCK_OUTPUT_FIELDS if field not in set(unlock_outputs)
    ]
    min_expected_label_rows = _int(handoff.get("post_return_min_expected_label_rows"))
    ready = bool(
        handoff.get("post_return_output_contract_ready") is True
        and not missing_required_outputs
        and not missing_unlock_outputs
        and min_expected_label_rows >= expected_rows
        and expected_rows > 0
        and unlock_artifacts
    )
    return {
        "ready": ready,
        "required_outputs": required_outputs,
        "unlock_outputs": unlock_outputs,
        "unlock_artifact_count": len(unlock_artifacts),
        "missing_required_outputs": missing_required_outputs,
        "missing_unlock_outputs": missing_unlock_outputs,
        "min_expected_label_rows": min_expected_label_rows,
    }


def _production_gpu_backend_status(summary: dict[str, Any], expected_rows: int) -> dict[str, Any]:
    backend_counts_raw = summary.get("backend_counts")
    backend_counts = backend_counts_raw if isinstance(backend_counts_raw, dict) else {}
    production_gpu_rows = 0
    non_production_rows = 0
    normalized_counts: dict[str, int] = {}
    for key, value in backend_counts.items():
        backend = _text(key).lower()
        count = _int(value)
        if not backend:
            continue
        normalized_counts[backend] = count
        if any(backend.startswith(prefix) for prefix in PRODUCTION_GPU_BACKEND_PREFIXES):
            production_gpu_rows += count
        if any(marker in backend for marker in NON_PRODUCTION_BACKEND_MARKERS):
            non_production_rows += count
    prod_mode = summary.get("prod_mode") is True
    require_rust_hip = summary.get("require_rust_hip") is True
    ready = bool(
        expected_rows > 0
        and prod_mode
        and require_rust_hip
        and production_gpu_rows >= expected_rows
        and non_production_rows == 0
    )
    return {
        "ready": ready,
        "backend_counts": normalized_counts,
        "production_gpu_rows": production_gpu_rows,
        "non_production_rows": non_production_rows,
        "prod_mode": prod_mode,
        "require_rust_hip": require_rust_hip,
    }


def build_residual_force_gpu_worker_return_receipt(
    *,
    handoff_packet: dict[str, Any],
    regeneration_queue_packet: dict[str, Any] | None = None,
    regeneration_summary_packet: dict[str, Any],
    derivation_validation_packet: dict[str, Any],
    regeneration_manifest_csv: str = DEFAULT_REGENERATION_MANIFEST_CSV,
    handoff_path: str = DEFAULT_HANDOFF_JSON,
    regeneration_queue_path: str = DEFAULT_REGENERATION_QUEUE_JSON,
    regeneration_summary_path: str = DEFAULT_REGENERATION_SUMMARY_JSON,
    derivation_validation_path: str = DEFAULT_DERIVATION_VALIDATION_JSON,
) -> dict[str, Any]:
    handoff = _summary(handoff_packet)
    queue_packet = regeneration_queue_packet or {}
    queue_artifact = _text(handoff.get("regeneration_queue_artifact")) or regeneration_queue_path
    full = _summary(regeneration_summary_packet)
    derivation = _summary(derivation_validation_packet)
    manifest = _manifest_counts(regeneration_manifest_csv)
    identity = _manifest_identity_coverage(
        queue_packet=queue_packet,
        queue_packet_path=queue_artifact,
        manifest_csv=regeneration_manifest_csv,
    )
    validation_chain = _handoff_validation_chain_status(handoff)
    promotion_ladder = _handoff_promotion_ladder_status(handoff)

    expected_rows = _int(handoff.get("queue_rows")) or _int(full.get("queue_rows"))
    output_contract = _handoff_output_contract_status(handoff, expected_rows)
    backend_status = _production_gpu_backend_status(full, expected_rows)
    handoff_ready = _bool(handoff.get("gpu_worker_handoff_ready"))
    summary_present = bool(full)
    summary_out_manifest_csv = _summary_out_manifest_csv(full)
    summary_out_manifest_csv_present = bool(summary_present and summary_out_manifest_csv)
    summary_out_manifest_csv_bound = bool(
        summary_present
        and summary_out_manifest_csv
        and _same_resolved_path(summary_out_manifest_csv, regeneration_manifest_csv)
    )
    summary_out_summary_json = _summary_out_summary_json(full)
    summary_out_summary_json_bound = bool(
        summary_present
        and summary_out_summary_json
        and _same_resolved_path(summary_out_summary_json, regeneration_summary_path)
    )
    summary_manifest_csv = _summary_manifest_csv(full)
    summary_processed_rows = _int(full.get("processed_rows"))
    summary_ok_rows = _int(full.get("ok_rows"))
    full_complete = bool(
        summary_present
        and expected_rows > 0
        and _int(full.get("queue_rows")) == expected_rows
        and summary_processed_rows >= expected_rows
        and summary_ok_rows >= expected_rows
        and _int(full.get("failed_rows")) == 0
        and full.get("aborted_early") is not True
    )
    summary_manifest_bound = bool(
        summary_present
        and summary_manifest_csv
        and _same_resolved_path(summary_manifest_csv, regeneration_manifest_csv)
    )
    manifest_complete = bool(
        manifest["manifest_present"]
        and not manifest.get("manifest_read_error")
        and expected_rows > 0
        and _int(manifest["manifest_row_count"]) >= expected_rows
        and _int(manifest["manifest_ok_row_count"]) >= expected_rows
        and _int(manifest["manifest_failed_row_count"]) == 0
        and _int(manifest["manifest_status_placeholder_count"]) == 0
        and _int(manifest["manifest_status_invalid_count"]) == 0
    )
    summary_manifest_row_counts_consistent = bool(
        summary_present
        and manifest["manifest_present"]
        and not manifest.get("manifest_read_error")
        and summary_processed_rows > 0
        and summary_ok_rows > 0
        and _int(manifest["manifest_row_count"]) == summary_processed_rows
        and _int(manifest["manifest_ok_row_count"]) == summary_ok_rows
    )
    manifest_npz_paths_complete = bool(
        manifest["manifest_present"]
        and not manifest.get("manifest_read_error")
        and expected_rows > 0
        and manifest.get("manifest_npz_path_column_present") is True
        and _int(manifest["manifest_npz_path_present_count"]) >= expected_rows
        and _int(manifest["manifest_ok_row_missing_npz_path_count"]) == 0
        and _int(manifest["manifest_operator_verified_missing_npz_path_count"]) == 0
    )
    manifest_npz_files_exist = bool(
        manifest_npz_paths_complete
        and _int(manifest["manifest_npz_file_existing_count"]) >= expected_rows
        and _int(manifest["manifest_npz_file_missing_count"]) == 0
        and _int(manifest["manifest_ok_row_missing_npz_file_count"]) == 0
        and _int(manifest["manifest_operator_verified_missing_npz_file_count"]) == 0
    )
    manifest_npz_files_valid = bool(
        manifest_npz_files_exist
        and _int(manifest["manifest_npz_file_valid_count"]) >= expected_rows
        and _int(manifest["manifest_npz_file_invalid_count"]) == 0
        and _int(manifest["manifest_ok_row_invalid_npz_file_count"]) == 0
        and _int(manifest["manifest_operator_verified_invalid_npz_file_count"]) == 0
    )
    manifest_npz_schema_valid = bool(
        manifest_npz_files_valid
        and _int(manifest["manifest_npz_schema_valid_count"]) >= expected_rows
        and _int(manifest["manifest_npz_schema_invalid_count"]) == 0
        and _int(manifest["manifest_ok_row_invalid_npz_schema_count"]) == 0
        and _int(manifest["manifest_operator_verified_invalid_npz_schema_count"]) == 0
    )
    manifest_npz_identity_valid = bool(
        manifest_npz_schema_valid
        and _int(identity["manifest_npz_identity_valid_count"]) >= expected_rows
        and _int(identity["manifest_npz_identity_invalid_count"]) == 0
        and _int(identity["manifest_ok_row_invalid_npz_identity_count"]) == 0
        and _int(identity["manifest_operator_verified_invalid_npz_identity_count"]) == 0
    )
    manifest_operator_verified = bool(
        manifest["manifest_present"]
        and not manifest.get("manifest_read_error")
        and expected_rows > 0
        and manifest.get("manifest_operator_verification_column_present") is True
        and _int(manifest["manifest_operator_verified_true_count"]) >= expected_rows
        and _int(manifest["manifest_operator_verification_placeholder_count"]) == 0
        and _int(manifest["manifest_operator_verification_false_count"]) == 0
        and _int(manifest["manifest_operator_verification_invalid_count"]) == 0
    )
    manifest_identity_ready = bool(manifest_complete and identity["identity_coverage_ready"])
    derivation_ready = _bool(derivation.get("delta_force_derivation_validation_ready"))
    derivation_npz_ready = bool(
        _int(derivation.get("existing_remapped_trajectory_npz_rows"))
        >= _int(derivation.get("effective_min_existing_npz_rows"))
        and _int(derivation.get("effective_min_existing_npz_rows")) > 0
    )
    derivation_samples_ready = bool(
        _int(derivation.get("derivation_input_sample_count"))
        >= _int(derivation.get("min_npz_probe_successes"))
        and _int(derivation.get("min_npz_probe_successes")) > 0
    )

    rows = [
        _row(
            "handoff_package_ready",
            "pass" if handoff_ready else "fail",
            f"gpu_worker_handoff_ready={handoff_ready};queue_rows={expected_rows}",
            "GPU worker handoff package was prepared for the same queue",
            "Build the GPU worker handoff package before accepting returned artifacts.",
            handoff_path,
        ),
        _row(
            "handoff_post_run_validation_chain_current",
            "pass" if validation_chain["ready"] else "fail",
            (
                f"post_run_validation_command_count={validation_chain['command_count']};"
                f"ordered={validation_chain['ordered']};"
                f"missing_markers={','.join(validation_chain['missing_markers'])}"
            ),
            "handoff post-run validation chain includes force receipt, force derivation, uncertainty policy, training-data, checkpoint, registry, architecture, and release audit rebuilds in order",
            "Rebuild the GPU worker handoff package so returned artifacts trigger the complete post-run validation chain.",
            handoff_path,
        ),
        _row(
            "handoff_post_return_promotion_ladder_current",
            "pass" if promotion_ladder["ready"] else "fail",
            (
                f"post_return_promotion_ladder_stage_count={promotion_ladder['stage_count']};"
                f"missing_ready_keys={','.join(promotion_ladder['missing_ready_keys'])}"
            ),
            "handoff package includes the post-return promotion ladder from GPU receipt through production_promotion_allowed, all_gaps_closed, and goal_complete",
            "Rebuild the GPU worker handoff package so returned artifacts are checked against the production inference promotion ladder.",
            handoff_path,
        ),
        _row(
            "handoff_post_return_output_contract_current",
            "pass" if output_contract["ready"] else "fail",
            (
                f"post_return_output_contract_ready={handoff.get('post_return_output_contract_ready')};"
                f"required_outputs={','.join(output_contract['required_outputs'])};"
                f"unlock_outputs={','.join(output_contract['unlock_outputs'])};"
                f"missing_required_outputs={','.join(output_contract['missing_required_outputs'])};"
                f"missing_unlock_outputs={','.join(output_contract['missing_unlock_outputs'])};"
                f"unlock_artifact_count={output_contract['unlock_artifact_count']};"
                f"min_expected_label_rows={output_contract['min_expected_label_rows']};"
                f"expected_rows={expected_rows}"
            ),
            "handoff package binds returned GPU force evidence to all required production output fields and minimum label rows",
            "Rebuild the GPU worker handoff package so returned force artifacts unlock delta_force, uncertainty, abstention_reason, and stage2_route_decision for checkpoint preflight.",
            handoff_path,
        ),
        _row(
            "full_regeneration_summary_complete",
            "pass" if full_complete else "fail",
            (
                f"summary_present={summary_present};queue_rows={full.get('queue_rows', 0)};"
                f"processed_rows={full.get('processed_rows', 0)};ok_rows={full.get('ok_rows', 0)};"
                f"failed_rows={full.get('failed_rows', 0)};aborted_early={full.get('aborted_early')}"
            ),
            "full regeneration summary has processed_rows>=queue_rows, ok_rows>=queue_rows, failed_rows=0, and no early abort",
            "Run the full GPU regeneration command and return the current summary JSON.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_summary_manifest_bound",
            "pass" if summary_manifest_bound else "fail",
            (
                f"summary_manifest_csv={summary_manifest_csv};"
                f"receipt_manifest_csv={regeneration_manifest_csv};"
                f"summary_manifest_bound={summary_manifest_bound}"
            ),
            "returned full-regeneration summary points to the same manifest CSV that this receipt verifies",
            "Return a summary JSON whose out_manifest_csv or artifacts.manifest_csv matches the returned manifest CSV.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_summary_out_manifest_csv_present",
            "pass" if summary_out_manifest_csv_present else "fail",
            (
                f"out_manifest_csv={summary_out_manifest_csv};"
                f"summary_out_manifest_csv_present={summary_out_manifest_csv_present}"
            ),
            "returned full-regeneration summary has top-level out_manifest_csv from the GPU worker summary template",
            "Return a summary JSON with top-level out_manifest_csv set to the returned manifest CSV.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_summary_out_manifest_csv_bound",
            "pass" if summary_out_manifest_csv_bound else "fail",
            (
                f"out_manifest_csv={summary_out_manifest_csv};"
                f"receipt_manifest_csv={regeneration_manifest_csv};"
                f"summary_out_manifest_csv_bound={summary_out_manifest_csv_bound}"
            ),
            "returned full-regeneration summary top-level out_manifest_csv matches the manifest CSV accepted by this receipt",
            "Return a summary JSON with top-level out_manifest_csv set to the same manifest CSV being returned.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_summary_out_summary_json_bound",
            "pass" if summary_out_summary_json_bound else "fail",
            (
                f"out_summary_json={summary_out_summary_json};"
                f"receipt_summary_json={regeneration_summary_path};"
                f"summary_out_summary_json_bound={summary_out_summary_json_bound}"
            ),
            "returned full-regeneration summary has top-level out_summary_json matching the summary JSON accepted by this receipt",
            "Return a summary JSON with top-level out_summary_json set to this returned summary JSON path.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_summary_manifest_row_counts_consistent",
            "pass" if summary_manifest_row_counts_consistent else "fail",
            (
                f"summary_processed_rows={summary_processed_rows};"
                f"summary_ok_rows={summary_ok_rows};"
                f"manifest_row_count={manifest['manifest_row_count']};"
                f"manifest_ok_row_count={manifest['manifest_ok_row_count']};"
                f"summary_manifest_row_counts_consistent={summary_manifest_row_counts_consistent}"
            ),
            "returned summary processed/ok rows match the returned manifest row/ok-row counts",
            "Return a summary JSON and manifest CSV from the same full GPU regeneration run.",
            regeneration_summary_path,
        ),
        _row(
            "production_gpu_backend_provenance",
            "pass" if backend_status["ready"] else "fail",
            (
                f"prod_mode={backend_status['prod_mode']};"
                f"require_rust_hip={backend_status['require_rust_hip']};"
                f"production_gpu_backend_rows={backend_status['production_gpu_rows']};"
                f"non_production_backend_rows={backend_status['non_production_rows']};"
                f"expected_rows={expected_rows};"
                f"backend_counts={json.dumps(backend_status['backend_counts'], sort_keys=True)}"
            ),
            "returned full-regeneration summary proves production GPU/HIP backend coverage for every expected queue row with no CPU diagnostic fallback rows",
            "Run the production handoff command with Rust/HIP GPU backend enabled; CPU diagnostic summaries cannot unlock production checkpoint promotion.",
            regeneration_summary_path,
        ),
        _row(
            "full_regeneration_manifest_complete",
            "pass" if manifest_complete else "fail",
            (
                f"manifest_present={manifest['manifest_present']};manifest_row_count={manifest['manifest_row_count']};"
                f"manifest_ok_row_count={manifest['manifest_ok_row_count']};"
                f"manifest_failed_row_count={manifest['manifest_failed_row_count']};"
                f"manifest_status_placeholder_count={manifest['manifest_status_placeholder_count']};"
                f"manifest_status_invalid_count={manifest['manifest_status_invalid_count']};"
                f"manifest_status_values={manifest['manifest_status_values']}"
            ),
            "full regeneration manifest has at least queue_rows rows with an allowed ok status and no failed, placeholder, or invalid status rows",
            "Return the full regeneration manifest CSV with status in ok, ok_npz_bundle, ok_regenerated_npz, or ok_full_regeneration for every completed queue row.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_npz_paths_complete",
            "pass" if manifest_npz_paths_complete else "fail",
            (
                f"npz_path_column_present={manifest['manifest_npz_path_column_present']};"
                f"npz_path_present_count={manifest['manifest_npz_path_present_count']};"
                f"npz_path_missing_count={manifest['manifest_npz_path_missing_count']};"
                f"ok_row_missing_npz_path_count={manifest['manifest_ok_row_missing_npz_path_count']};"
                f"operator_verified_missing_npz_path_count={manifest['manifest_operator_verified_missing_npz_path_count']}"
            ),
            "full regeneration manifest has a generated NPZ path for every ok and operator-verified queue row",
            "Return the full regeneration manifest with expected_regenerated_trajectory_npz, trajectory_npz, output_npz, or generated_npz filled for every completed queue row.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_npz_files_exist",
            "pass" if manifest_npz_files_exist else "fail",
            (
                f"npz_file_existing_count={manifest['manifest_npz_file_existing_count']};"
                f"npz_file_missing_count={manifest['manifest_npz_file_missing_count']};"
                f"ok_row_missing_npz_file_count={manifest['manifest_ok_row_missing_npz_file_count']};"
                f"operator_verified_missing_npz_file_count={manifest['manifest_operator_verified_missing_npz_file_count']}"
            ),
            "full regeneration manifest NPZ paths resolve to local files for every ok and operator-verified row",
            "Return or restore the regenerated NPZ files at the manifest paths before marking the GPU return receipt ready.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_npz_files_valid",
            "pass" if manifest_npz_files_valid else "fail",
            (
                f"npz_file_valid_count={manifest['manifest_npz_file_valid_count']};"
                f"npz_file_invalid_count={manifest['manifest_npz_file_invalid_count']};"
                f"ok_row_invalid_npz_file_count={manifest['manifest_ok_row_invalid_npz_file_count']};"
                f"operator_verified_invalid_npz_file_count={manifest['manifest_operator_verified_invalid_npz_file_count']}"
            ),
            "full regeneration manifest NPZ files are readable NPZ bundles for every ok and operator-verified row",
            "Return readable non-empty NPZ bundles at the manifest paths before accepting the GPU return.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_npz_schema_valid",
            "pass" if manifest_npz_schema_valid else "fail",
            (
                f"npz_schema_valid_count={manifest['manifest_npz_schema_valid_count']};"
                f"npz_schema_invalid_count={manifest['manifest_npz_schema_invalid_count']};"
                f"ok_row_invalid_npz_schema_count={manifest['manifest_ok_row_invalid_npz_schema_count']};"
                f"operator_verified_invalid_npz_schema_count={manifest['manifest_operator_verified_invalid_npz_schema_count']};"
                f"required_npz_schema_keys={','.join(REQUIRED_NPZ_SCHEMA_KEYS)}"
            ),
            "full regeneration manifest NPZ files contain protein_ca [P,3] and ligand_frames [T,L,3] arrays for every ok and operator-verified row",
            "Return regenerated trajectory NPZ bundles with protein_ca and ligand_frames arrays matching the production trajectory schema.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_npz_identity_valid",
            "pass" if manifest_npz_identity_valid else "fail",
            (
                f"npz_identity_valid_count={identity['manifest_npz_identity_valid_count']};"
                f"npz_identity_invalid_count={identity['manifest_npz_identity_invalid_count']};"
                f"ok_row_invalid_npz_identity_count={identity['manifest_ok_row_invalid_npz_identity_count']};"
                f"operator_verified_invalid_npz_identity_count={identity['manifest_operator_verified_invalid_npz_identity_count']};"
                f"required_npz_identity_keys={','.join(REQUIRED_NPZ_IDENTITY_KEYS)}"
            ),
            "full regeneration manifest NPZ files contain queue identity metadata matching the prepared queue rows",
            "Return regenerated trajectory NPZ bundles with queue_id metadata matching the identity-locked manifest and queue.",
            regeneration_manifest_csv,
        ),
        _row(
            "full_regeneration_manifest_operator_verified",
            "pass" if manifest_operator_verified else "fail",
            (
                f"operator_column_present={manifest['manifest_operator_verification_column_present']};"
                f"operator_verified_true_count={manifest['manifest_operator_verified_true_count']};"
                f"operator_placeholder_count={manifest['manifest_operator_verification_placeholder_count']};"
                f"operator_false_count={manifest['manifest_operator_verification_false_count']};"
                f"operator_invalid_count={manifest['manifest_operator_verification_invalid_count']}"
            ),
            "full regeneration manifest has operator_verified_npz_exists=true for every expected queue row",
            "Return the full regeneration manifest after verifying each regenerated NPZ exists and marking operator_verified_npz_exists=true.",
            regeneration_manifest_csv,
        ),
        _row(
            "queue_manifest_identity_coverage",
            "pass" if manifest_identity_ready else "fail",
            (
                f"queue_identity_rows={identity['queue_identity_row_count']};"
                f"queue_id_count={identity['queue_id_count']};expected_npz_count={identity['expected_npz_count']};"
                f"queue_fingerprint_count={identity['queue_fingerprint_count']};"
                f"manifest_identity_rows={identity['manifest_identity_row_count']};"
                f"manifest_queue_id_count={identity['manifest_queue_id_count']};"
                f"manifest_npz_count={identity['manifest_npz_count']};"
                f"manifest_fingerprint_count={identity['manifest_fingerprint_count']};"
                f"matched_queue_ids={identity['manifest_matched_queue_id_count']};"
                f"matched_expected_npz={identity['manifest_matched_expected_npz_count']};"
                f"matched_queue_fingerprints={identity['manifest_matched_queue_fingerprint_count']};"
                f"missing_queue_ids={identity['missing_queue_id_count']};"
                f"missing_expected_npz={identity['missing_expected_npz_count']};"
                f"missing_queue_fingerprints={identity['missing_queue_fingerprint_count']};"
                f"unexpected_manifest_queue_ids={identity['unexpected_manifest_queue_id_count']};"
                f"unexpected_manifest_npz={identity['unexpected_manifest_npz_count']};"
                f"unexpected_manifest_queue_fingerprints={identity['unexpected_manifest_queue_fingerprint_count']};"
                f"duplicate_manifest_queue_ids={identity['manifest_duplicate_queue_id_count']};"
                f"duplicate_manifest_npz={identity['manifest_duplicate_npz_count']};"
                f"duplicate_manifest_queue_fingerprints={identity['manifest_duplicate_queue_fingerprint_count']}"
            ),
            "returned manifest covers the prepared regeneration queue by queue_id, expected regenerated NPZ path, or queue fingerprint with no unexpected or duplicate identity rows",
            "Return a manifest that includes exactly one queue_id, expected/generated NPZ path, or queue fingerprint for every handoff queue row.",
            queue_artifact,
        ),
        _row(
            "post_run_force_derivation_validation",
            "pass" if derivation_ready and derivation_npz_ready and derivation_samples_ready else "fail",
            (
                f"delta_force_derivation_validation_ready={derivation_ready};"
                f"existing_remapped_trajectory_npz_rows={derivation.get('existing_remapped_trajectory_npz_rows', 0)};"
                f"effective_min_existing_npz_rows={derivation.get('effective_min_existing_npz_rows', 0)};"
                f"derivation_input_sample_count={derivation.get('derivation_input_sample_count', 0)};"
                f"min_npz_probe_successes={derivation.get('min_npz_probe_successes', 0)}"
            ),
            "post-run derivation validation accepts the regenerated NPZ bundles as force-derivation inputs",
            "Rerun residual_force_derivation_validation after restoring/generated NPZ bundles.",
            derivation_validation_path,
        ),
    ]
    blockers = [row["check_id"] for row in rows if row["status"] != "pass"]
    first_blocked = next((row for row in rows if row["status"] != "pass"), None)
    ready = not blockers
    summary = {
        "packet_type": "residual_force_gpu_worker_return_receipt",
        "status": "residual_force_gpu_worker_return_receipt_ready" if ready else "blocked_residual_force_gpu_worker_return_receipt",
        "gpu_worker_return_receipt_ready": ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "expected_queue_rows": expected_rows,
        "handoff_post_run_validation_chain_current": validation_chain["ready"],
        "handoff_post_run_validation_command_count": validation_chain["command_count"],
        "handoff_post_run_validation_missing_markers": validation_chain["missing_markers"],
        "handoff_post_run_validation_ordered": validation_chain["ordered"],
        "handoff_post_return_promotion_ladder_current": promotion_ladder["ready"],
        "handoff_post_return_promotion_ladder_stage_count": promotion_ladder["stage_count"],
        "handoff_post_return_promotion_ladder_missing_ready_keys": promotion_ladder["missing_ready_keys"],
        "handoff_post_return_output_contract_current": output_contract["ready"],
        "handoff_post_return_required_production_output_fields": output_contract["required_outputs"],
        "handoff_post_return_gpu_unlock_output_fields": output_contract["unlock_outputs"],
        "handoff_post_return_output_contract_missing_required_outputs": output_contract["missing_required_outputs"],
        "handoff_post_return_output_contract_missing_unlock_outputs": output_contract["missing_unlock_outputs"],
        "handoff_post_return_output_contract_unlock_artifact_count": output_contract["unlock_artifact_count"],
        "handoff_post_return_min_expected_label_rows": output_contract["min_expected_label_rows"],
        "full_regeneration_summary_present": summary_present,
        "full_regeneration_summary_complete": full_complete,
        "full_regeneration_summary_manifest_bound": summary_manifest_bound,
        "full_regeneration_summary_out_manifest_csv_present": summary_out_manifest_csv_present,
        "full_regeneration_summary_out_manifest_csv_bound": summary_out_manifest_csv_bound,
        "full_regeneration_summary_out_summary_json_bound": summary_out_summary_json_bound,
        "full_regeneration_summary_manifest_row_counts_consistent": summary_manifest_row_counts_consistent,
        "production_gpu_backend_provenance_ready": backend_status["ready"],
        "production_gpu_backend_counts": backend_status["backend_counts"],
        "production_gpu_backend_rows": _int(backend_status["production_gpu_rows"]),
        "production_gpu_backend_non_production_rows": _int(backend_status["non_production_rows"]),
        "production_gpu_backend_prod_mode": backend_status["prod_mode"],
        "production_gpu_backend_require_rust_hip": backend_status["require_rust_hip"],
        "summary_out_manifest_csv": summary_out_manifest_csv,
        "summary_out_summary_json": summary_out_summary_json,
        "summary_manifest_csv": summary_manifest_csv,
        "full_regeneration_manifest_present": bool(manifest["manifest_present"]),
        "full_regeneration_manifest_complete": manifest_complete,
        "full_regeneration_manifest_npz_paths_complete": manifest_npz_paths_complete,
        "full_regeneration_manifest_npz_files_exist": manifest_npz_files_exist,
        "full_regeneration_manifest_npz_files_valid": manifest_npz_files_valid,
        "full_regeneration_manifest_npz_schema_valid": manifest_npz_schema_valid,
        "full_regeneration_manifest_npz_identity_valid": manifest_npz_identity_valid,
        "full_regeneration_manifest_operator_verified": manifest_operator_verified,
        "full_regeneration_summary_artifact": regeneration_summary_path,
        "full_regeneration_manifest_artifact": regeneration_manifest_csv,
        "manifest_npz_path_column_present": manifest["manifest_npz_path_column_present"],
        "manifest_npz_path_present_count": _int(manifest["manifest_npz_path_present_count"]),
        "manifest_npz_path_missing_count": _int(manifest["manifest_npz_path_missing_count"]),
        "manifest_ok_row_missing_npz_path_count": _int(manifest["manifest_ok_row_missing_npz_path_count"]),
        "manifest_operator_verified_missing_npz_path_count": _int(
            manifest["manifest_operator_verified_missing_npz_path_count"]
        ),
        "manifest_npz_file_existing_count": _int(manifest["manifest_npz_file_existing_count"]),
        "manifest_npz_file_missing_count": _int(manifest["manifest_npz_file_missing_count"]),
        "manifest_ok_row_missing_npz_file_count": _int(manifest["manifest_ok_row_missing_npz_file_count"]),
        "manifest_operator_verified_missing_npz_file_count": _int(
            manifest["manifest_operator_verified_missing_npz_file_count"]
        ),
        "manifest_npz_file_valid_count": _int(manifest["manifest_npz_file_valid_count"]),
        "manifest_npz_file_invalid_count": _int(manifest["manifest_npz_file_invalid_count"]),
        "manifest_ok_row_invalid_npz_file_count": _int(manifest["manifest_ok_row_invalid_npz_file_count"]),
        "manifest_operator_verified_invalid_npz_file_count": _int(
            manifest["manifest_operator_verified_invalid_npz_file_count"]
        ),
        "manifest_npz_schema_valid_count": _int(manifest["manifest_npz_schema_valid_count"]),
        "manifest_npz_schema_invalid_count": _int(manifest["manifest_npz_schema_invalid_count"]),
        "manifest_ok_row_invalid_npz_schema_count": _int(manifest["manifest_ok_row_invalid_npz_schema_count"]),
        "manifest_operator_verified_invalid_npz_schema_count": _int(
            manifest["manifest_operator_verified_invalid_npz_schema_count"]
        ),
        "manifest_npz_identity_valid_count": _int(identity["manifest_npz_identity_valid_count"]),
        "manifest_npz_identity_invalid_count": _int(identity["manifest_npz_identity_invalid_count"]),
        "manifest_ok_row_invalid_npz_identity_count": _int(
            identity["manifest_ok_row_invalid_npz_identity_count"]
        ),
        "manifest_operator_verified_invalid_npz_identity_count": _int(
            identity["manifest_operator_verified_invalid_npz_identity_count"]
        ),
        "manifest_operator_verification_column_present": manifest["manifest_operator_verification_column_present"],
        "manifest_operator_verified_true_count": _int(manifest["manifest_operator_verified_true_count"]),
        "manifest_operator_verification_placeholder_count": _int(manifest["manifest_operator_verification_placeholder_count"]),
        "manifest_operator_verification_false_count": _int(manifest["manifest_operator_verification_false_count"]),
        "manifest_operator_verification_invalid_count": _int(manifest["manifest_operator_verification_invalid_count"]),
        "queue_manifest_identity_coverage_ready": manifest_identity_ready,
        "queue_identity_artifact": queue_artifact,
        "queue_identity_row_count": _int(identity["queue_identity_row_count"]),
        "queue_id_count": _int(identity["queue_id_count"]),
        "expected_npz_count": _int(identity["expected_npz_count"]),
        "queue_fingerprint_count": _int(identity["queue_fingerprint_count"]),
        "manifest_identity_row_count": _int(identity["manifest_identity_row_count"]),
        "manifest_queue_id_count": _int(identity["manifest_queue_id_count"]),
        "manifest_npz_count": _int(identity["manifest_npz_count"]),
        "manifest_fingerprint_count": _int(identity["manifest_fingerprint_count"]),
        "manifest_duplicate_queue_id_count": _int(identity["manifest_duplicate_queue_id_count"]),
        "manifest_duplicate_npz_count": _int(identity["manifest_duplicate_npz_count"]),
        "manifest_duplicate_queue_fingerprint_count": _int(identity["manifest_duplicate_queue_fingerprint_count"]),
        "manifest_duplicate_identity_count": _int(identity["manifest_duplicate_identity_count"]),
        "manifest_matched_queue_id_count": _int(identity["manifest_matched_queue_id_count"]),
        "manifest_matched_expected_npz_count": _int(identity["manifest_matched_expected_npz_count"]),
        "manifest_matched_queue_fingerprint_count": _int(identity["manifest_matched_queue_fingerprint_count"]),
        "missing_queue_id_count": _int(identity["missing_queue_id_count"]),
        "missing_expected_npz_count": _int(identity["missing_expected_npz_count"]),
        "missing_queue_fingerprint_count": _int(identity["missing_queue_fingerprint_count"]),
        "unexpected_manifest_queue_id_count": _int(identity["unexpected_manifest_queue_id_count"]),
        "unexpected_manifest_npz_count": _int(identity["unexpected_manifest_npz_count"]),
        "unexpected_manifest_queue_fingerprint_count": _int(identity["unexpected_manifest_queue_fingerprint_count"]),
        "summary_processed_rows": summary_processed_rows,
        "summary_ok_rows": summary_ok_rows,
        "summary_failed_rows": _int(full.get("failed_rows")),
        "summary_aborted_early": full.get("aborted_early") is True,
        "manifest_row_count": _int(manifest["manifest_row_count"]),
        "manifest_ok_row_count": _int(manifest["manifest_ok_row_count"]),
        "manifest_failed_row_count": _int(manifest["manifest_failed_row_count"]),
        "manifest_status_placeholder_count": _int(manifest["manifest_status_placeholder_count"]),
        "manifest_status_invalid_count": _int(manifest["manifest_status_invalid_count"]),
        "manifest_allowed_ok_status_values": sorted(MANIFEST_OK_STATUS_VALUES),
        "post_run_derivation_validation_ready": derivation_ready,
        "post_run_derivation_npz_ready": derivation_npz_ready,
        "post_run_derivation_samples_ready": derivation_samples_ready,
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "source_artifacts": [handoff_path, queue_artifact, regeneration_summary_path, regeneration_manifest_csv, derivation_validation_path],
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "GPU worker return receipt is ready; rebuild energy/force label work order and training-data contract."
            if ready
            else first_blocked["next_action"] if first_blocked else "Repair the blocked GPU worker return receipt checks."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Return Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- gpu_worker_return_receipt_ready: `{s['gpu_worker_return_receipt_ready']}`",
        f"- expected_queue_rows: `{s['expected_queue_rows']}`",
        f"- summary_ok_rows: `{s['summary_ok_rows']}`",
        f"- full_regeneration_summary_manifest_bound: `{s['full_regeneration_summary_manifest_bound']}`",
        f"- full_regeneration_summary_out_manifest_csv_present: `{s['full_regeneration_summary_out_manifest_csv_present']}`",
        f"- full_regeneration_summary_out_manifest_csv_bound: `{s['full_regeneration_summary_out_manifest_csv_bound']}`",
        f"- full_regeneration_summary_out_summary_json_bound: `{s['full_regeneration_summary_out_summary_json_bound']}`",
        f"- full_regeneration_summary_manifest_row_counts_consistent: `{s['full_regeneration_summary_manifest_row_counts_consistent']}`",
        f"- production_gpu_backend_provenance_ready: `{s['production_gpu_backend_provenance_ready']}`",
        f"- production_gpu_backend_rows: `{s['production_gpu_backend_rows']}`",
        f"- production_gpu_backend_non_production_rows: `{s['production_gpu_backend_non_production_rows']}`",
        f"- production_gpu_backend_prod_mode: `{s['production_gpu_backend_prod_mode']}`",
        f"- production_gpu_backend_require_rust_hip: `{s['production_gpu_backend_require_rust_hip']}`",
        f"- summary_out_manifest_csv: `{s['summary_out_manifest_csv']}`",
        f"- summary_out_summary_json: `{s['summary_out_summary_json']}`",
        f"- summary_manifest_csv: `{s['summary_manifest_csv']}`",
        f"- manifest_ok_row_count: `{s['manifest_ok_row_count']}`",
        f"- full_regeneration_manifest_npz_paths_complete: `{s['full_regeneration_manifest_npz_paths_complete']}`",
        f"- manifest_npz_path_present_count: `{s['manifest_npz_path_present_count']}`",
        f"- manifest_ok_row_missing_npz_path_count: `{s['manifest_ok_row_missing_npz_path_count']}`",
        f"- full_regeneration_manifest_npz_files_exist: `{s['full_regeneration_manifest_npz_files_exist']}`",
        f"- manifest_npz_file_existing_count: `{s['manifest_npz_file_existing_count']}`",
        f"- full_regeneration_manifest_npz_files_valid: `{s['full_regeneration_manifest_npz_files_valid']}`",
        f"- manifest_npz_file_valid_count: `{s['manifest_npz_file_valid_count']}`",
        f"- full_regeneration_manifest_npz_schema_valid: `{s['full_regeneration_manifest_npz_schema_valid']}`",
        f"- manifest_npz_schema_valid_count: `{s['manifest_npz_schema_valid_count']}`",
        f"- full_regeneration_manifest_npz_identity_valid: `{s['full_regeneration_manifest_npz_identity_valid']}`",
        f"- manifest_npz_identity_valid_count: `{s['manifest_npz_identity_valid_count']}`",
        f"- full_regeneration_manifest_operator_verified: `{s['full_regeneration_manifest_operator_verified']}`",
        f"- manifest_operator_verified_true_count: `{s['manifest_operator_verified_true_count']}`",
        f"- queue_manifest_identity_coverage_ready: `{s['queue_manifest_identity_coverage_ready']}`",
        f"- manifest_matched_queue_id_count: `{s['manifest_matched_queue_id_count']}`",
        f"- manifest_matched_expected_npz_count: `{s['manifest_matched_expected_npz_count']}`",
        f"- manifest_matched_queue_fingerprint_count: `{s['manifest_matched_queue_fingerprint_count']}`",
        f"- handoff_post_return_promotion_ladder_current: `{s['handoff_post_return_promotion_ladder_current']}`",
        f"- handoff_post_return_promotion_ladder_stage_count: `{s['handoff_post_return_promotion_ladder_stage_count']}`",
        f"- handoff_post_return_output_contract_current: `{s['handoff_post_return_output_contract_current']}`",
        f"- handoff_post_return_gpu_unlock_output_fields: `{','.join(s['handoff_post_return_gpu_unlock_output_fields'])}`",
        f"- handoff_post_return_min_expected_label_rows: `{s['handoff_post_return_min_expected_label_rows']}`",
        f"- post_run_derivation_validation_ready: `{s['post_run_derivation_validation_ready']}`",
        f"- blockers: `{','.join(s['blockers'])}`",
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
    parser = argparse.ArgumentParser(description="Build residual force GPU worker return receipt.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--regeneration-queue-json", default=DEFAULT_REGENERATION_QUEUE_JSON)
    parser.add_argument("--regeneration-summary-json", default=DEFAULT_REGENERATION_SUMMARY_JSON)
    parser.add_argument("--regeneration-manifest-csv", default=DEFAULT_REGENERATION_MANIFEST_CSV)
    parser.add_argument("--derivation-validation-json", default=DEFAULT_DERIVATION_VALIDATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_force_gpu_worker_return_receipt(
        handoff_packet=_read_json_if_present(args.handoff_json),
        regeneration_queue_packet=_read_json_if_present(args.regeneration_queue_json),
        regeneration_summary_packet=_read_json_if_present(args.regeneration_summary_json),
        derivation_validation_packet=_read_json_if_present(args.derivation_validation_json),
        regeneration_manifest_csv=args.regeneration_manifest_csv,
        handoff_path=args.handoff_json,
        regeneration_queue_path=args.regeneration_queue_json,
        regeneration_summary_path=args.regeneration_summary_json,
        derivation_validation_path=args.derivation_validation_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
