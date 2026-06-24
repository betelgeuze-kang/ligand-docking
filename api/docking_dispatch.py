"""Bridge product docking ledger records to the durable simulation queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.config import settings
from api.docking_outbox import (
    enqueue_job_with_outbox,
    mark_outbox_delivered,
    mark_outbox_failed,
    pending_outbox_events,
)
from api.job_store import SQLiteJobStore, get_configured_job_store
from api.runner_profile_contract import (
    EXECUTION_MODE_RESTRICTED_PRODUCTION,
    EXECUTION_MODE_SMOKE,
    validate_runner_profile_execution_contract,
)
from api.validated_runner import _runner_script, validate_profile_readiness
from betelgeuze_product.atomic_io import atomic_write_json
from betelgeuze_product.engine_dispatch import DEFAULT_RUNNER_PROFILE, engine_roadmap_ready
from betelgeuze_product.job_orchestration import append_job_event, read_job_record
from betelgeuze_product.job_terminal_state import apply_terminal_job_state
from betelgeuze_product.payload_privacy import sanitize_request_for_ledger
from betelgeuze_product.private_payload_store import PrivatePayloadStore

INTERNAL_SMOKE_ACTORS = {"tier_alpha_dispatch_smoke"}
_SQLITE_TERMINAL_STATUSES = {"completed", "failed"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _atomic_write_job_record(jobs_dir: Path, record: dict[str, Any]) -> Path:
    path = jobs_dir / f"{_text(record.get('job_id'))}.json"
    return atomic_write_json(
        path,
        sanitize_request_for_ledger(record),
        mode=0o600,
    )


def _internal_smoke_authorized(
    record: dict[str, Any],
    *,
    allow_internal_smoke: bool,
) -> bool:
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


def _private_materialization_ready(record: dict[str, Any]) -> tuple[bool, str]:
    reference = _text(record.get("private_payload_ref"))
    request_sha = _text(
        record.get("private_payload_request_sha256") or record.get("request_sha256")
    )
    job_id = _text(record.get("job_id"))
    if not reference:
        return False, "private_payload_ref_missing"
    if not request_sha:
        return False, "private_payload_request_sha256_missing"
    try:
        inspection = PrivatePayloadStore.from_settings(settings).inspect(
            reference,
            expected_job_id=job_id,
            expected_request_sha256=request_sha,
        )
    except Exception as exc:
        return False, f"private_payload_not_ready:{exc}"
    expected_count = int(record.get("ligand_count") or 0)
    observed_count = int(inspection.get("private_payload_ligand_count") or 0)
    if expected_count <= 0 or observed_count != expected_count:
        return False, "private_payload_ligand_count_mismatch"
    return True, "private_payload_ready"


def _load_profile_contract(
    record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
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
    if manifest.get("customer_submission_allowed") is not None and bool(
        manifest.get("customer_submission_allowed")
    ) != bool(execution.get("customer_submission_allowed")):
        raise PermissionError(
            f"runner_profile_customer_submission_contract_mismatch:{profile_id}"
        )
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

    mode = _text(execution.get("execution_mode"))
    if mode == EXECUTION_MODE_SMOKE:
        if not _internal_smoke_authorized(
            record,
            allow_internal_smoke=allow_internal_smoke,
        ):
            return False, f"runner_profile_not_customer_submission_allowed:{profile_id}"
        if execution.get("synthetic_input_allowed") is not True:
            return False, f"runner_profile_synthetic_input_not_allowed:{profile_id}"
    elif mode == EXECUTION_MODE_RESTRICTED_PRODUCTION:
        if execution.get("customer_submission_allowed") is not True:
            return False, f"runner_profile_not_customer_submission_allowed:{profile_id}"
        materialization_ready, materialization_reason = _private_materialization_ready(record)
        if not materialization_ready:
            return False, f"runner_input_materialization_not_ready:{materialization_reason}"
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
            "runner_customer_submission_allowed": execution.get(
                "customer_submission_allowed"
            )
            is True,
            "runner_synthetic_input_allowed": execution.get("synthetic_input_allowed")
            is True,
            "runner_production_claim_allowed": execution.get("production_claim_allowed")
            is True,
            "runner_customer_pose_emission_allowed": execution.get(
                "customer_pose_emission_allowed"
            )
            is True,
            "allow_synthetic_ligand_input": bool(allow_synthetic_ligand_input),
            "private_payload_ref": _text(record.get("private_payload_ref")),
            "private_payload_request_sha256": _text(
                record.get("private_payload_request_sha256")
                or record.get("request_sha256")
            ),
            "private_payload_key_id": _text(record.get("private_payload_key_id")),
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
            "worker_state": "completed_fail_closed"
            if completed
            else "failed_retryable_fail_closed",
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
    _atomic_write_job_record(jobs_dir, updated)
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
    result = enqueue_job_with_outbox(
        store,
        job_id=job_id,
        request=simulate_request,
        event_payload={
            "job_id": job_id,
            "request_sha256": _text(record.get("request_sha256")),
            "ledger_event": "worker_dispatch_enqueued",
        },
        status="submitted",
    )
    sqlite_status = _text(result.get("sqlite_status")) or "submitted"
    return {
        **result,
        "simulate_request": simulate_request,
        "created": result.get("job_created") is True,
        "terminal": sqlite_status in _SQLITE_TERMINAL_STATUSES,
    }


def mark_ledger_dispatched(
    jobs_dir: Path,
    job_id: str,
    *,
    worker_id: str = "",
) -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        raise FileNotFoundError(f"docking ledger record not found: {job_id}")
    if record.get("worker_dispatch_enqueued") is True:
        return record
    updated = append_job_event(
        record,
        event_type="worker_dispatch_enqueued",
        reason="transactional_outbox_to_sqlite_worker_dispatch",
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
    _atomic_write_job_record(jobs_dir, updated)
    return updated


def reconcile_pending_dispatch_outbox(
    jobs_dir: Path,
    *,
    store: SQLiteJobStore | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    job_store = store or get_configured_job_store()
    outcomes: list[dict[str, Any]] = []
    for event in pending_outbox_events(job_store, limit=limit):
        event_id = _text(event.get("event_id"))
        job_id = _text(event.get("job_id"))
        try:
            record = read_job_record(jobs_dir, job_id)
            if not record:
                raise FileNotFoundError(f"docking ledger record not found: {job_id}")
            sqlite_record = job_store.get_job(job_id) or {}
            if _text(sqlite_record.get("status")) not in _SQLITE_TERMINAL_STATUSES:
                mark_ledger_dispatched(jobs_dir, job_id)
            mark_outbox_delivered(job_store, event_id)
            outcomes.append(
                {
                    "event_id": event_id,
                    "job_id": job_id,
                    "delivered": True,
                }
            )
        except Exception as exc:
            mark_outbox_failed(job_store, event_id, str(exc))
            outcomes.append(
                {
                    "event_id": event_id,
                    "job_id": job_id,
                    "delivered": False,
                    "error": str(exc),
                }
            )
    return outcomes


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
        return {
            "dispatched": False,
            "reason": reason,
            "job_id": _text(record.get("job_id")),
        }

    _, execution, _ = _load_profile_contract(record)
    allow_synthetic = bool(
        _internal_smoke_authorized(
            record,
            allow_internal_smoke=allow_internal_smoke,
        )
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
    event_id = _text(enqueue_payload.get("event_id"))
    if enqueue_payload.get("terminal") is True:
        if event_id:
            mark_outbox_delivered(job_store, event_id)
        return {
            "dispatched": False,
            "reason": "already_terminal_in_job_store",
            "job_id": _text(record.get("job_id")),
            "enqueue": enqueue_payload,
        }

    try:
        ledger = mark_ledger_dispatched(jobs_dir, _text(record.get("job_id")))
        if event_id:
            mark_outbox_delivered(job_store, event_id)
    except Exception as exc:
        if event_id:
            mark_outbox_failed(job_store, event_id, str(exc))
        return {
            "dispatched": False,
            "reason": "dispatch_outbox_delivery_failed",
            "job_id": _text(record.get("job_id")),
            "error": str(exc),
            "enqueue": enqueue_payload,
        }

    return {
        "dispatched": True,
        "reason": "already_enqueued"
        if enqueue_payload.get("already_present")
        else reason,
        "job_id": _text(record.get("job_id")),
        "enqueue": enqueue_payload,
        "idempotent_replay": enqueue_payload.get("already_present") is True,
        "execution_mode": _text(execution.get("execution_mode")),
        "synthetic_input_authorized": allow_synthetic,
        "ledger_status": _text(ledger.get("progress_state")),
    }


def dispatch_ready_docking_jobs(
    jobs_dir: Path,
    *,
    store: SQLiteJobStore | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    job_store = store or get_configured_job_store()
    reconcile_pending_dispatch_outbox(
        jobs_dir,
        store=job_store,
        limit=max(1, int(limit) * 4),
    )
    results: list[dict[str, Any]] = []
    if not jobs_dir.exists():
        return results
    for path in sorted(jobs_dir.glob("*.json"), key=lambda item: item.stat().st_mtime):
        if len(results) >= max(1, int(limit)):
            break
        record = read_job_record(jobs_dir, path.stem)
        if not record:
            continue
        outcome = dispatch_docking_job_if_eligible(
            record,
            jobs_dir=jobs_dir,
            store=job_store,
        )
        if outcome.get("dispatched"):
            results.append(outcome)
    return results
