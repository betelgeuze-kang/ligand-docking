"""Bridge product docking ledger records to SQLite simulation worker queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.config import settings
from api.job_store import SQLiteJobStore, get_configured_job_store
from api.request_privacy import sanitize_request_for_ledger
from api.runner_profile_contract import (
    EXECUTION_MODE_RESTRICTED_PRODUCTION,
    EXECUTION_MODE_SMOKE,
    validate_runner_profile_execution_contract,
)
from api.validated_runner import _runner_script, validate_profile_readiness
from betelgeuze_product.engine_dispatch import DEFAULT_RUNNER_PROFILE, engine_roadmap_ready
from betelgeuze_product.job_orchestration import append_job_event, read_job_record, write_job_record
from betelgeuze_product.structured_reason import reason_fields
from betelgeuze_product.job_terminal_state import apply_terminal_job_state

INTERNAL_SMOKE_ACTORS = {"tier_alpha_dispatch_smoke"}
_RAW_MATERIALIZATION_FIELDS = ("smiles", "ligand_smiles", "inchi")
_SQLITE_TERMINAL_STATUSES = {"completed", "failed"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _internal_smoke_authorized(record: dict[str, Any], *, allow_internal_smoke: bool) -> bool:
    manifest = record.get("engine_dispatch_manifest")
    legacy_internal_record = bool(
        isinstance(manifest, dict)
        and not _text(manifest.get("execution_mode"))
        and not _text(record.get("source_host"))
        and not _text(record.get("customer_id"))
        and not _text(record.get("user_id"))
        and not isinstance(record.get("intake_payload"), dict)
    )
    return bool(
        allow_internal_smoke
        or _text(record.get("source_host")) in INTERNAL_SMOKE_ACTORS
        or legacy_internal_record
    )


def _materialization_row_ready(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    # A private payload reference is not considered ready until a resolver is
    # implemented in the materializers. This prevents dispatch from admitting
    # an opaque reference that the worker cannot actually dereference.
    return any(_text(row.get(key)) for key in _RAW_MATERIALIZATION_FIELDS)


def _record_materialization_ready(record: dict[str, Any]) -> bool:
    expected_count = int(record.get("ligand_count", 0) or 0)
    candidates: list[list[Any]] = []
    materialization_ligands = record.get("materialization_ligands")
    if isinstance(materialization_ligands, list) and materialization_ligands:
        candidates.append(materialization_ligands)
    intake = record.get("intake_payload")
    if isinstance(intake, dict):
        intake_ligands = intake.get("ligands")
        if isinstance(intake_ligands, list) and intake_ligands:
            candidates.append(intake_ligands)
    return any(
        rows
        and (expected_count <= 0 or len(rows) == expected_count)
        and all(_materialization_row_ready(row) for row in rows)
        for rows in candidates
    )


def _load_profile_contract(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    manifest = record.get("engine_dispatch_manifest", {})
    if not isinstance(manifest, dict):
        raise PermissionError("missing_engine_dispatch_manifest")
    profile_id = _text(manifest.get("runner_profile_id")) or DEFAULT_RUNNER_PROFILE
    profiles_dir = Path(settings.api_validated_runner_profiles_path)
    profile_path = profiles_dir / f"{profile_id}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"runner_profile_missing:{profile_id}")
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PermissionError(f"runner_profile_unreadable:{profile_id}") from exc
    if not isinstance(profile, dict):
        raise PermissionError(f"runner_profile_not_object:{profile_id}")
    if profile.get("enabled") is not True:
        raise PermissionError(f"runner_profile_disabled:{profile_id}")
    runner_script_path = _runner_script(profile)
    readiness = validate_profile_readiness(profile, runner_script_path=runner_script_path)
    execution = validate_runner_profile_execution_contract(profile, require_explicit=True)

    manifest_mode = _text(manifest.get("execution_mode"))
    if manifest_mode and manifest_mode != execution["execution_mode"]:
        raise PermissionError(f"runner_profile_execution_mode_mismatch:{profile_id}")
    return readiness, execution, profile_id


def is_dispatch_eligible(
    record: dict[str, Any],
    *,
    allow_internal_smoke: bool = False,
) -> tuple[bool, str]:
    if _text(record.get("status")) != "accepted_fail_closed":
        return False, "status_not_accepted_fail_closed"
    if _text(record.get("queue_status")) != "queued_fail_closed":
        return False, "queue_status_not_queued_fail_closed"
    if _text(record.get("validation_status")) != "pass":
        return False, "validation_status_not_pass"
    if record.get("worker_dispatch_enqueued") is True:
        return False, "already_dispatched"
    if not bool(record.get("engine_dispatch_ready", False)) and not engine_roadmap_ready():
        return False, "engine_dispatch_not_ready"
    if record.get("scope_claim_allowed_for_request") is False:
        return False, "scope_claim_not_allowed"
    if not bool(settings.api_validated_runner_enabled):
        return False, "api_validated_runner_disabled"

    try:
        _, execution, profile_id = _load_profile_contract(record)
    except Exception as exc:
        return False, f"runner_profile_not_ready:{exc}"

    internal_smoke = _internal_smoke_authorized(
        record,
        allow_internal_smoke=allow_internal_smoke,
    )
    mode = _text(execution.get("execution_mode"))
    if mode == EXECUTION_MODE_SMOKE:
        if not internal_smoke:
            return False, f"runner_profile_not_customer_submission_allowed:{profile_id}"
        if execution.get("synthetic_input_allowed") is not True:
            return False, f"runner_profile_synthetic_input_not_allowed:{profile_id}"
    elif mode == EXECUTION_MODE_RESTRICTED_PRODUCTION:
        if execution.get("customer_submission_allowed") is not True:
            return False, f"runner_profile_not_customer_submission_allowed:{profile_id}"
        if not _record_materialization_ready(record):
            return False, "runner_input_materialization_not_ready"
    else:
        return False, f"runner_profile_execution_mode_not_supported:{profile_id}"
    return True, "eligible"


def build_simulate_request(
    record: dict[str, Any],
    *,
    execution_contract: dict[str, Any] | None = None,
    allow_synthetic_ligand_input: bool = False,
) -> dict[str, Any]:
    manifest = record.get("engine_dispatch_manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    profile_id = _text(manifest.get("runner_profile_id")) or DEFAULT_RUNNER_PROFILE
    execution = dict(execution_contract or {})
    return {
        "runner_profile_id": profile_id,
        "target_name": _text(record.get("target_id")),
        "runner_profile_params": {
            "docking_job_id": _text(record.get("job_id")),
            "request_sha256": _text(record.get("request_sha256")),
            "family": _text(record.get("family")),
            "ligand_count": int(record.get("ligand_count", 0) or 0),
            "structure_source_kind": _text(record.get("structure_source_kind")),
            "ligand_model_hint": _text(manifest.get("ligand_model_hint")) or "auto",
            "engine_dispatch_manifest": manifest,
            "runner_execution_mode": _text(execution.get("execution_mode")),
            "runner_customer_submission_allowed": execution.get("customer_submission_allowed") is True,
            "runner_synthetic_input_allowed": execution.get("synthetic_input_allowed") is True,
            "runner_production_claim_allowed": execution.get("production_claim_allowed") is True,
            "runner_customer_pose_emission_allowed": execution.get("customer_pose_emission_allowed") is True,
            "allow_synthetic_ligand_input": bool(allow_synthetic_ligand_input),
            "intake_payload": record.get("intake_payload", {}),
            "ligands": list((record.get("intake_payload") or {}).get("ligands", []) or []),
        },
    }


def sync_ledger_from_simulation_result(
    jobs_dir: Path,
    job_id: str,
    *,
    status: str,
    result_file: str = "",
    error: str = "",
    worker_id: str = "",
) -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        return {"synced": False, "reason": "ledger_not_found", "job_id": job_id}
    completed = _text(status) == "completed"
    event_type = "worker_dispatch_completed" if completed else "worker_dispatch_failed"
    updated = append_job_event(
        record,
        event_type=event_type,
        reason=_text(error or status),
        actor=worker_id or "api_worker",
        details={
            "worker_state": "completed_fail_closed" if completed else "failed_retryable_fail_closed",
            "progress_state": event_type if completed else "worker_failed_retryable",
            "current_step": event_type if completed else "worker_failure_recorded",
            "simulation_status": _text(status),
            "simulation_result_file": _text(result_file),
            "execution_enabled": False,
            "docking_results_emitted": False,
        },
    )
    updated = apply_terminal_job_state(
        updated,
        simulation_status=_text(status),
        result_file=_text(result_file),
        error=_text(error),
    )
    write_job_record(jobs_dir, updated)
    return {
        "synced": True,
        "job_id": job_id,
        "status": _text(status),
        "ledger_status": _text(updated.get("status")),
        "worker_state": _text(updated.get("worker_state")),
        "terminal_state": True,
    }


def enqueue_docking_job(
    store: SQLiteJobStore,
    record: dict[str, Any],
    *,
    execution_contract: dict[str, Any] | None = None,
    allow_synthetic_ligand_input: bool = False,
) -> dict[str, Any]:
    job_id = _text(record.get("job_id"))
    if not job_id:
        raise ValueError("docking record missing job_id")
    simulate_request = build_simulate_request(
        record,
        execution_contract=execution_contract,
        allow_synthetic_ligand_input=allow_synthetic_ligand_input,
    )
    stored, created = store.create_job_if_absent(
        job_id,
        simulate_request,
        status="submitted",
    )
    if not created:
        expected_request = sanitize_request_for_ledger(simulate_request)
        if dict(stored.get("request") or {}) != expected_request:
            raise ValueError(f"docking dispatch idempotency conflict for job_id={job_id}")
    sqlite_status = _text(stored.get("status")) or "submitted"
    return {
        "job_id": job_id,
        "simulate_request": simulate_request,
        "sqlite_status": sqlite_status,
        "created": created,
        "already_present": not created,
        "terminal": sqlite_status in _SQLITE_TERMINAL_STATUSES,
    }


def mark_ledger_dispatched(jobs_dir: Path, job_id: str, *, worker_id: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        raise FileNotFoundError(f"docking ledger record not found: {job_id}")
    if record.get("worker_dispatch_enqueued") is True:
        return record
    updated = append_job_event(
        record,
        event_type="worker_dispatch_enqueued",
        reason="ledger_to_sqlite_worker_dispatch",
        actor=worker_id or "api_docking_dispatch",
        details={
            "progress_state": "worker_dispatch_enqueued",
            "current_step": "worker_dispatch_enqueued",
            "worker_dispatch_enqueued": True,
            "execution_enabled": False,
            "docking_results_emitted": False,
        },
    )
    updated["worker_dispatch_enqueued"] = True
    updated["progress_state"] = "worker_dispatch_enqueued"
    updated["current_step"] = "worker_dispatch_enqueued"
    write_job_record(jobs_dir, updated)
    return updated


def dispatch_docking_job_if_eligible(
    record: dict[str, Any],
    *,
    jobs_dir: Path,
    store: SQLiteJobStore | None = None,
    allow_internal_smoke: bool = False,
) -> dict[str, Any]:
    eligible, reason = is_dispatch_eligible(
        record,
        allow_internal_smoke=allow_internal_smoke,
    )
    if not eligible:
        return {"dispatched": False, "job_id": _text(record.get("job_id")), **reason_fields(reason)}

    _, execution, _ = _load_profile_contract(record)
    internal_smoke = _internal_smoke_authorized(
        record,
        allow_internal_smoke=allow_internal_smoke,
    )
    allow_synthetic = bool(
        internal_smoke
        and execution.get("execution_mode") == EXECUTION_MODE_SMOKE
        and execution.get("synthetic_input_allowed") is True
    )
    job_store = store or get_configured_job_store()
    enqueue_payload = enqueue_docking_job(
        job_store,
        record,
        execution_contract=execution,
        allow_synthetic_ligand_input=allow_synthetic,
    )
    if enqueue_payload.get("terminal") is True:
        return {
            "dispatched": False,
            "job_id": _text(record.get("job_id")),
            "enqueue": enqueue_payload,
            **reason_fields("already_terminal_in_job_store"),
        }
    ledger = mark_ledger_dispatched(jobs_dir, _text(record.get("job_id")))
    dispatch_reason = "already_enqueued" if enqueue_payload.get("already_present") else reason
    return {
        "dispatched": True,
        "job_id": _text(record.get("job_id")),
        "enqueue": enqueue_payload,
        "idempotent_replay": enqueue_payload.get("already_present") is True,
        "execution_mode": _text(execution.get("execution_mode")),
        "synthetic_input_authorized": allow_synthetic,
        "ledger_status": _text(ledger.get("progress_state")),
        **reason_fields(dispatch_reason),
    }


def dispatch_ready_docking_jobs(
    jobs_dir: Path,
    *,
    store: SQLiteJobStore | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    job_store = store or get_configured_job_store()
    results: list[dict[str, Any]] = []
    if not jobs_dir.exists():
        return results
    for path in sorted(jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime):
        if len(results) >= max(1, int(limit)):
            break
        record = read_job_record(jobs_dir, path.stem)
        if not record:
            continue
        outcome = dispatch_docking_job_if_eligible(record, jobs_dir=jobs_dir, store=job_store)
        if outcome.get("dispatched"):
            results.append(outcome)
    return results
