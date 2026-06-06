"""Bridge product docking ledger records to SQLite simulation worker queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from api.config import settings
from api.job_store import SQLiteJobStore
from api.validated_runner import _runner_script, validate_profile_readiness
from betelgeuze_product.engine_dispatch import DEFAULT_RUNNER_PROFILE, engine_roadmap_ready
from betelgeuze_product.job_orchestration import append_job_event, read_job_record, write_job_record


def is_dispatch_eligible(record: dict[str, Any]) -> tuple[bool, str]:
    if str(record.get("status", "")).strip() != "accepted_fail_closed":
        return False, "status_not_accepted_fail_closed"
    if str(record.get("queue_status", "")).strip() != "queued_fail_closed":
        return False, "queue_status_not_queued_fail_closed"
    if str(record.get("validation_status", "")).strip() != "pass":
        return False, "validation_status_not_pass"
    if not bool(record.get("engine_dispatch_ready", False)) and not engine_roadmap_ready():
        return False, "engine_dispatch_not_ready"
    if record.get("scope_claim_allowed_for_request") is False:
        return False, "scope_claim_not_allowed"
    if not bool(settings.api_validated_runner_enabled):
        return False, "api_validated_runner_disabled"
    manifest = record.get("engine_dispatch_manifest", {})
    if not isinstance(manifest, dict):
        return False, "missing_engine_dispatch_manifest"
    profile_id = str(manifest.get("runner_profile_id", DEFAULT_RUNNER_PROFILE) or DEFAULT_RUNNER_PROFILE)
    profiles_dir = Path(settings.api_validated_runner_profiles_path)
    profile_path = profiles_dir / f"{profile_id}.json"
    if not profile_path.exists():
        return False, f"runner_profile_missing:{profile_id}"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, f"runner_profile_unreadable:{profile_id}"
    if not bool(profile.get("enabled", False)):
        return False, f"runner_profile_disabled:{profile_id}"
    try:
        runner_script_path = _runner_script(profile)
        validate_profile_readiness(profile, runner_script_path=runner_script_path)
    except Exception as exc:
        return False, f"runner_profile_not_ready:{exc}"
    if bool(record.get("worker_dispatch_enqueued", False)):
        return False, "already_dispatched"
    return True, "eligible"


def build_simulate_request(record: dict[str, Any]) -> dict[str, Any]:
    manifest = record.get("engine_dispatch_manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    profile_id = str(manifest.get("runner_profile_id", DEFAULT_RUNNER_PROFILE) or DEFAULT_RUNNER_PROFILE)
    return {
        "runner_profile_id": profile_id,
        "target_name": str(record.get("target_id", "")),
        "runner_profile_params": {
            "docking_job_id": str(record.get("job_id", "")),
            "request_sha256": str(record.get("request_sha256", "")),
            "family": str(record.get("family", "")),
            "ligand_count": int(record.get("ligand_count", 0) or 0),
            "structure_source_kind": str(record.get("structure_source_kind", "")),
            "ligand_model_hint": str(manifest.get("ligand_model_hint", "auto")),
            "engine_dispatch_manifest": manifest,
        },
    }


def enqueue_docking_job(store: SQLiteJobStore, record: dict[str, Any]) -> dict[str, Any]:
    job_id = str(record.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("docking record missing job_id")
    simulate_request = build_simulate_request(record)
    store.create_job(job_id, simulate_request, status="submitted")
    return {
        "job_id": job_id,
        "simulate_request": simulate_request,
        "sqlite_status": "submitted",
    }


def mark_ledger_dispatched(jobs_dir: Path, job_id: str, *, worker_id: str = "") -> dict[str, Any]:
    record = read_job_record(jobs_dir, job_id)
    if not record:
        raise FileNotFoundError(f"docking ledger record not found: {job_id}")
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
) -> dict[str, Any]:
    eligible, reason = is_dispatch_eligible(record)
    if not eligible:
        return {"dispatched": False, "reason": reason, "job_id": str(record.get("job_id", ""))}
    job_store = store or SQLiteJobStore(settings.api_job_store_path)
    enqueue_payload = enqueue_docking_job(job_store, record)
    ledger = mark_ledger_dispatched(jobs_dir, str(record.get("job_id", "")))
    return {
        "dispatched": True,
        "reason": reason,
        "job_id": str(record.get("job_id", "")),
        "enqueue": enqueue_payload,
        "ledger_status": str(ledger.get("progress_state", "")),
    }


def dispatch_ready_docking_jobs(
    jobs_dir: Path,
    *,
    store: SQLiteJobStore | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    job_store = store or SQLiteJobStore(settings.api_job_store_path)
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
