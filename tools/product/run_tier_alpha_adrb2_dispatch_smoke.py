#!/usr/bin/env python3
"""Run Tier α ADRB2 API dispatch smoke and record live ledger evidence (Package A A-40)."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROOT_TEXT = str(ROOT)
if sys.path[:1] != [ROOT_TEXT]:
    try:
        sys.path.remove(ROOT_TEXT)
    except ValueError:
        pass
    sys.path.insert(0, ROOT_TEXT)

DEFAULT_WORKSPACE = "runs/tier_alpha_dispatch_smoke/current"
DEFAULT_OUT_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_JOB_PREFIX = "tier_alpha_adrb2_smoke"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_QUALIFICATION_KEYS = (
    "validated_runner_namespace_runtime_qualified",
    "validated_runner_namespace_runtime_receipt_schema_version",
    "validated_runner_namespace_runtime_receipt_sha256",
    "validated_runner_namespace_runtime_receipt_issued_at_utc",
    "validated_runner_namespace_runtime_receipt_expires_at_utc",
)
_RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

CLAIM_BOUNDARY = (
    "Tier α ADRB2 dispatch smoke only; submits one restricted gpcr docking ledger row, dispatches to the "
    "SQLite worker queue with API_VALIDATED_RUNNER_ENABLED=1, and waits for worker completion. "
    "It does not emit customer-facing poses or mutate external state."
)

SMOKE_PAYLOAD: dict[str, Any] = {
    "request_type": "structure_analysis_ligand_docking",
    "family": "gpcr",
    "target_id": "ADRB2",
    "pdb_content": (
        "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
        "ATOM      2  CA  ALA A   2      13.104  13.207  14.321  1.00 10.00           C\n"
    ),
    "ligands": [{"ligand_id": "tier_alpha_smoke_lig_1", "smiles": "CCO"}],
}


def _configure_runtime(
    *,
    workspace: Path,
    job_id: str,
    runner_enabled: bool = True,
    runner_timeout_seconds: int = 240,
) -> None:
    results = workspace / "results"
    jobs = results / "product_docking_jobs"
    results.mkdir(parents=True, exist_ok=True)
    jobs.mkdir(parents=True, exist_ok=True)
    os.environ["BETELGEUZE_REPO_ROOT"] = str(ROOT)
    os.environ["RESULTS_STORAGE_PATH"] = str(results)
    os.environ["API_JOB_STORE_PATH"] = str(results / f"{job_id}.sqlite3")
    os.environ["API_VALIDATED_RUNNER_ENABLED"] = "1" if runner_enabled else "0"
    os.environ["API_VALIDATED_RUNNER_PROFILES_PATH"] = str(ROOT / "config/api_validated_runner_profiles")
    os.environ["API_VALIDATED_RUNNER_TIMEOUT_SECONDS"] = str(max(5, int(runner_timeout_seconds)))
    os.environ["API_RESULT_MANIFEST_SIGNING_KEY"] = os.environ.get(
        "API_RESULT_MANIFEST_SIGNING_KEY",
        "tier-alpha-local-smoke-signing-key",
    )
    os.environ["API_RESULT_MANIFEST_KEY_ID"] = os.environ.get("API_RESULT_MANIFEST_KEY_ID", "tier-alpha-local")


def _reload_settings() -> None:
    import importlib

    import api.config as config_mod

    importlib.reload(config_mod)


def _adrb2_smoke_job_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def _runner_timeout_for_smoke(timeout_seconds: int) -> int:
    return max(5, max(30, int(timeout_seconds)) - 60)


async def _run_operator_qualified_profile(
    job_id: str,
    request_data: dict[str, Any],
) -> None:
    """Run the internal smoke profile without opening the public submission path."""

    from api.validated_runner import execute_validated_runner_profile
    from api.validated_runner_execution_evidence import (
        EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY,
        EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY,
        TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE,
        TIER_ALPHA_ADRB2_RUNNER_PROFILE_ID,
        TIER_ALPHA_ADRB2_SOURCE_ACTOR,
    )

    params = request_data.get("runner_profile_params")
    if not isinstance(params, dict) or (
        request_data.get("runner_profile_id") != TIER_ALPHA_ADRB2_RUNNER_PROFILE_ID
        or request_data.get("target_name") != "ADRB2"
        or params.get("family") != "gpcr"
        or params.get("docking_job_id") != job_id
    ):
        raise PermissionError("Tier alpha smoke execution identity is invalid")
    operator_request = dict(request_data)
    operator_request[EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY] = (
        TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE
    )
    operator_request[EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY] = (
        TIER_ALPHA_ADRB2_SOURCE_ACTOR
    )

    await execute_validated_runner_profile(
        job_id,
        operator_request,
        require_customer_submission_allowed=False,
    )


def _empty_runtime_qualification() -> dict[str, Any]:
    return {
        "validated_runner_namespace_runtime_qualified": False,
        "validated_runner_namespace_runtime_receipt_schema_version": "",
        "validated_runner_namespace_runtime_receipt_sha256": "",
        "validated_runner_namespace_runtime_receipt_issued_at_utc": "",
        "validated_runner_namespace_runtime_receipt_expires_at_utc": "",
    }


def _validated_runner_runtime_manifest_binding(
    manifest_payload: dict[str, Any],
    status_payload: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Validate the exact signed receipt record against the published run status."""

    from api.validated_runner_runtime_qualification import (
        MAX_RECEIPT_VALIDITY,
        RECEIPT_SCHEMA_VERSION,
    )

    empty = _empty_runtime_qualification()
    worker_provenance = manifest_payload.get("worker_provenance")
    if not isinstance(worker_provenance, dict):
        return False, empty
    qualification = worker_provenance.get(
        "validated_runner_runtime_qualification"
    )
    if not isinstance(qualification, dict) or set(qualification) != set(
        _RUNTIME_QUALIFICATION_KEYS
    ):
        return False, empty

    qualified = qualification[_RUNTIME_QUALIFICATION_KEYS[0]]
    schema_version = qualification[_RUNTIME_QUALIFICATION_KEYS[1]]
    receipt_sha256 = qualification[_RUNTIME_QUALIFICATION_KEYS[2]]
    issued_at_utc = qualification[_RUNTIME_QUALIFICATION_KEYS[3]]
    expires_at_utc = qualification[_RUNTIME_QUALIFICATION_KEYS[4]]
    if qualified is not True or type(qualified) is not bool:
        return False, empty
    if type(schema_version) is not str or schema_version != RECEIPT_SCHEMA_VERSION:
        return False, empty
    if type(receipt_sha256) is not str or _SHA256_RE.fullmatch(receipt_sha256) is None:
        return False, empty
    if type(issued_at_utc) is not str or type(expires_at_utc) is not str:
        return False, empty
    try:
        issued_at = datetime.strptime(
            issued_at_utc,
            _RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT,
        ).replace(tzinfo=timezone.utc)
        expires_at = datetime.strptime(
            expires_at_utc,
            _RUNTIME_QUALIFICATION_TIMESTAMP_FORMAT,
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return False, empty
    if expires_at <= issued_at or expires_at - issued_at > MAX_RECEIPT_VALIDITY:
        return False, empty
    if any(
        type(status_payload.get(key)) is not type(qualification[key])
        or status_payload.get(key) != qualification[key]
        for key in _RUNTIME_QUALIFICATION_KEYS
    ):
        return False, empty
    return True, dict(qualification)


def _expected_tier_alpha_execution_evidence(job_id: str) -> dict[str, Any]:
    from api.validated_runner_execution_evidence import (
        tier_alpha_adrb2_execution_evidence,
    )

    return tier_alpha_adrb2_execution_evidence(job_id)


def _validated_runner_execution_manifest_binding(
    manifest_payload: dict[str, Any],
    status_payload: dict[str, Any],
    *,
    job_id: str,
) -> bool:
    from api.validated_runner_execution_evidence import (
        EXECUTION_EVIDENCE_PROVENANCE_KEY,
        validate_validated_runner_execution_evidence,
    )

    worker_provenance = manifest_payload.get("worker_provenance")
    if not isinstance(worker_provenance, dict):
        return False
    signed_evidence = worker_provenance.get(EXECUTION_EVIDENCE_PROVENANCE_KEY)
    try:
        validated_evidence = validate_validated_runner_execution_evidence(
            signed_evidence
        )
    except ValueError:
        return False
    expected = _expected_tier_alpha_execution_evidence(job_id)
    return bool(
        validated_evidence == expected
        and status_payload.get(EXECUTION_EVIDENCE_PROVENANCE_KEY) == expected
    )


def _read_confined_json_with_sha256(
    root: Path,
    path: Path,
    *,
    maximum_bytes: int,
) -> tuple[dict[str, Any], str]:
    """Read one bounded regular JSON file from a pinned, no-follow handle."""

    try:
        from api.artifact_access import open_confined_regular_file

        _, handle = open_confined_regular_file(
            root,
            path,
            label="Tier alpha smoke artifact",
        )
        with handle:
            raw = handle.read(maximum_bytes + 1)
    except Exception:
        return {}, ""
    if len(raw) > maximum_bytes:
        return {}, ""
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, ""
    if not isinstance(payload, dict):
        return {}, ""
    return payload, hashlib.sha256(raw).hexdigest()


def run_tier_alpha_adrb2_dispatch_smoke(
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    job_id: str | None = None,
    timeout_seconds: int = 1800,
    runner_timeout_seconds: int | None = None,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        workspace_path = ROOT / workspace_path
    resolved_job_id = job_id or _adrb2_smoke_job_id(DEFAULT_JOB_PREFIX)
    resolved_runner_timeout_seconds = (
        _runner_timeout_for_smoke(timeout_seconds)
        if runner_timeout_seconds is None
        else max(5, int(runner_timeout_seconds))
    )
    _configure_runtime(
        workspace=workspace_path,
        job_id=resolved_job_id,
        runner_enabled=True,
        runner_timeout_seconds=resolved_runner_timeout_seconds,
    )
    _reload_settings()

    from api.config import settings
    from api.docking_dispatch import dispatch_docking_job_if_eligible
    from api.job_store import SQLiteJobStore
    from api.worker import process_next_job_once
    from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
    from betelgeuze_product.job_orchestration import read_job_record

    jobs_dir = Path(settings.results_storage_path) / "product_docking_jobs"

    record = build_docking_job_record(SMOKE_PAYLOAD, job_id=resolved_job_id, source_host="tier_alpha_dispatch_smoke")
    persist_docking_job_record(record, jobs_dir)

    dispatch_outcome = dispatch_docking_job_if_eligible(
        read_job_record(jobs_dir, resolved_job_id) or record,
        jobs_dir=jobs_dir,
        store=SQLiteJobStore(settings.api_job_store_path),
    )

    worker_id = "tier-alpha-adrb2-smoke-worker"
    store = SQLiteJobStore(settings.api_job_store_path)
    deadline = time.monotonic() + max(30, int(timeout_seconds))
    worker_ran = False
    sqlite_status = ""
    last_error = ""
    drain_timed_out = False

    async def _drain_queue() -> None:
        nonlocal worker_ran, sqlite_status, last_error
        while time.monotonic() < deadline:
            ledger = read_job_record(jobs_dir, resolved_job_id) or {}
            if _text(ledger.get("worker_state")) in {"completed_fail_closed", "failed_fail_closed"}:
                simulation_state = _text(ledger.get("simulation_sync_status"))
                sqlite_status = "completed" if simulation_state == "completed" else simulation_state or sqlite_status
                return
            result = await process_next_job_once(
                store,
                worker_id=worker_id,
                runner=_run_operator_qualified_profile,
                lease_seconds=int(os.environ.get("API_WORKER_LEASE_SECONDS", "300")),
                heartbeat_interval_seconds=float(os.environ.get("API_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30")),
                retry_on_failure=False,
            )
            if result is not None:
                worker_ran = True
                sqlite_status = str(result.get("status", ""))
                last_error = str(result.get("error", "") or "")
                if sqlite_status in {"completed", "failed"}:
                    return
            ledger = read_job_record(jobs_dir, resolved_job_id) or {}
            if _text(ledger.get("worker_state")) in {"completed_fail_closed", "failed_fail_closed"}:
                return
            await asyncio.sleep(float(poll_seconds))

    if dispatch_outcome.get("dispatched") is not True:
        last_error = f"dispatch_not_enqueued:{_text(dispatch_outcome.get('reason'))}"
    else:
        try:
            asyncio.run(asyncio.wait_for(_drain_queue(), timeout=max(1.0, deadline - time.monotonic())))
        except asyncio.TimeoutError:
            drain_timed_out = True
            last_error = "tier_alpha_dispatch_smoke_timeout"

    ledger = read_job_record(jobs_dir, resolved_job_id) or {}
    worker_state = _text(ledger.get("worker_state"))
    simulation_sync = _text(ledger.get("simulation_sync_status"))
    job_result_root = Path(settings.results_storage_path) / resolved_job_id
    completed_record = store.get_job(resolved_job_id) or {}
    published_status_path = _text(completed_record.get("published_status_path"))
    status_json = Path(published_status_path) if published_status_path else Path("")
    status_payload, _ = _read_confined_json_with_sha256(
        job_result_root,
        status_json,
        maximum_bytes=16 * 1024 * 1024,
    )
    result_path: Path | None = None
    result_manifest_path: Path | None = None
    result_artifacts_verified = False
    result_manifest_signature_verified = False
    result_manifest_status = ""
    result_manifest_key_id = ""
    manifest_payload: dict[str, Any] = {}
    result_manifest_sha256 = ""
    try:
        from api.artifact_access import verify_completed_result_artifacts

        verified_artifacts = verify_completed_result_artifacts(
            job_id=resolved_job_id,
            record=completed_record,
            status_data=status_payload,
            result_root=job_result_root,
            signing_key=settings.api_result_manifest_signing_key,
            expected_key_id=settings.api_result_manifest_key_id,
        )
        try:
            result_path = verified_artifacts.result_path
            result_manifest_path = verified_artifacts.manifest_path
            manifest_payload = verified_artifacts.manifest
            independently_read_manifest, result_manifest_sha256 = (
                _read_confined_json_with_sha256(
                    job_result_root,
                    result_manifest_path,
                    maximum_bytes=1024 * 1024,
                )
            )
            result_artifacts_verified = bool(
                independently_read_manifest == manifest_payload
                and result_manifest_sha256
            )
        finally:
            verified_artifacts.close()
    except Exception:
        result_artifacts_verified = False
        manifest_payload = {}
        result_manifest_sha256 = ""

    if result_artifacts_verified:
        result_manifest_status = _text(manifest_payload.get("status"))
        result_manifest_key_id = _text(manifest_payload.get("signature_key_id"))
        result_manifest_signature_verified = True

    runtime_binding_shape_verified, runtime_qualification = (
        _validated_runner_runtime_manifest_binding(
            manifest_payload,
            status_payload,
        )
    )
    execution_evidence_binding_verified = (
        _validated_runner_execution_manifest_binding(
            manifest_payload,
            status_payload,
            job_id=resolved_job_id,
        )
    )
    result_manifest_status_verified = bool(
        result_artifacts_verified
        and result_manifest_signature_verified
        and result_manifest_status == "completed"
        and _text(manifest_payload.get("job_id")) == resolved_job_id
        and _text(status_payload.get("job_id")) == resolved_job_id
        and _text(status_payload.get("status")) == "completed"
    )
    runtime_manifest_binding_verified = bool(
        result_manifest_status_verified
        and runtime_binding_shape_verified
        and execution_evidence_binding_verified
    )
    ledger_result_binding_verified = bool(
        result_artifacts_verified
        and result_path is not None
        and _text(ledger.get("simulation_result_file")) == str(result_path)
    )
    if not runtime_manifest_binding_verified:
        runtime_qualification = _empty_runtime_qualification()

    success = bool(
        not drain_timed_out
        and worker_state == "completed_fail_closed"
        and simulation_sync == "completed"
        and runtime_manifest_binding_verified
        and ledger_result_binding_verified
    )
    return {
        "summary": {
            "packet_type": "tier_alpha_adrb2_dispatch_smoke",
            "status": "tier_alpha_adrb2_dispatch_smoke_pass" if success else "tier_alpha_adrb2_dispatch_smoke_failed",
            "evidence_mode": "live_job" if success else "live_job_failed",
            "api_validated_runner_enabled": settings.api_validated_runner_enabled,
            "workspace": str(workspace_path.relative_to(ROOT) if workspace_path.is_relative_to(ROOT) else workspace_path),
            "claim_boundary": CLAIM_BOUNDARY,
            "validated_runner_namespace_runtime_manifest_binding_verified": (
                runtime_manifest_binding_verified
            ),
            "validated_runner_execution_evidence_manifest_binding_verified": (
                execution_evidence_binding_verified
            ),
            "validated_result_artifacts_verified": result_artifacts_verified,
            "ledger_result_binding_verified": ledger_result_binding_verified,
            **runtime_qualification,
        },
        "job_id": resolved_job_id,
        "ledger_worker_state": worker_state or "not_started_fail_closed",
        "simulation_sync_status": simulation_sync,
        "dispatch_outcome": dispatch_outcome,
        "worker_ran": worker_ran,
        "sqlite_job_status": sqlite_status,
        "worker_error": last_error,
        "drain_timed_out": drain_timed_out,
        "timeout_seconds": max(30, int(timeout_seconds)),
        "runner_timeout_seconds": resolved_runner_timeout_seconds,
        "jobs_dir": str(jobs_dir.relative_to(ROOT) if jobs_dir.is_relative_to(ROOT) else jobs_dir),
        "htvs_summary_exists": result_artifacts_verified,
        "result_file": str(result_path) if result_artifacts_verified else "",
        "status_json": str(status_json) if status_payload else "",
        "result_manifest": (
            str(result_manifest_path) if result_artifacts_verified else ""
        ),
        "result_manifest_exists": result_artifacts_verified,
        "result_manifest_sha256": result_manifest_sha256,
        "result_manifest_signature_verified": result_manifest_signature_verified,
        "result_manifest_status": result_manifest_status,
        "result_manifest_status_verified": result_manifest_status_verified,
        "result_manifest_key_id": result_manifest_key_id,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Tier α ADRB2 dispatch smoke with API_VALIDATED_RUNNER_ENABLED=1.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--job-id", default="")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--runner-timeout-seconds", type=int, default=0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = run_tier_alpha_adrb2_dispatch_smoke(
        workspace=args.workspace,
        job_id=_text(args.job_id) or None,
        timeout_seconds=max(30, int(args.timeout_seconds)),
        runner_timeout_seconds=(
            max(5, int(args.runner_timeout_seconds))
            if int(args.runner_timeout_seconds or 0) > 0
            else None
        ),
    )
    out = ROOT / args.out_json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["summary"]["status"], "job_id": payload["job_id"], "out_json": str(out)}))
    if payload["summary"]["status"] != "tier_alpha_adrb2_dispatch_smoke_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
