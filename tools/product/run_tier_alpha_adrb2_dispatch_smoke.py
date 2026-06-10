#!/usr/bin/env python3
"""Run Tier α ADRB2 API dispatch smoke and record live ledger evidence (Package A A-40)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORKSPACE = "runs/tier_alpha_dispatch_smoke/current"
DEFAULT_OUT_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_JOB_PREFIX = "tier_alpha_adrb2_smoke"

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


def _configure_runtime(*, workspace: Path, runner_enabled: bool = True) -> None:
    results = workspace / "results"
    jobs = results / "product_docking_jobs"
    results.mkdir(parents=True, exist_ok=True)
    jobs.mkdir(parents=True, exist_ok=True)
    os.environ["BETELGEUZE_REPO_ROOT"] = str(ROOT)
    os.environ["RESULTS_STORAGE_PATH"] = str(results)
    os.environ["API_JOB_STORE_PATH"] = str(results / "api_jobs.sqlite3")
    os.environ["API_VALIDATED_RUNNER_ENABLED"] = "1" if runner_enabled else "0"
    os.environ["API_VALIDATED_RUNNER_PROFILES_PATH"] = str(ROOT / "config/api_validated_runner_profiles")
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


def run_tier_alpha_adrb2_dispatch_smoke(
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    job_id: str | None = None,
    timeout_seconds: int = 1800,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        workspace_path = ROOT / workspace_path
    _configure_runtime(workspace=workspace_path, runner_enabled=True)
    _reload_settings()

    from api.config import settings
    from api.docking_dispatch import dispatch_docking_job_if_eligible
    from api.job_store import SQLiteJobStore
    from api.worker import process_next_job_once
    from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
    from betelgeuze_product.job_orchestration import read_job_record

    resolved_job_id = job_id or _adrb2_smoke_job_id(DEFAULT_JOB_PREFIX)
    jobs_dir = Path(settings.results_storage_path) / "product_docking_jobs"

    record = build_docking_job_record(SMOKE_PAYLOAD, job_id=resolved_job_id, source_host="tier_alpha_dispatch_smoke")
    persist_docking_job_record(record, jobs_dir)

    dispatch_outcome = dispatch_docking_job_if_eligible(
        read_job_record(jobs_dir, resolved_job_id) or record,
        jobs_dir=jobs_dir,
        store=SQLiteJobStore(settings.api_job_store_path),
    )

    store = SQLiteJobStore(settings.api_job_store_path)
    worker_id = "tier-alpha-adrb2-smoke-worker"
    deadline = time.monotonic() + max(30, int(timeout_seconds))
    worker_ran = False
    sqlite_status = ""
    last_error = ""

    async def _drain_queue() -> None:
        nonlocal worker_ran, sqlite_status, last_error
        while time.monotonic() < deadline:
            result = await process_next_job_once(
                store,
                worker_id=worker_id,
                lease_seconds=int(os.environ.get("API_WORKER_LEASE_SECONDS", "300")),
                heartbeat_interval_seconds=float(os.environ.get("API_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30")),
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

    asyncio.run(_drain_queue())

    ledger = read_job_record(jobs_dir, resolved_job_id) or {}
    worker_state = _text(ledger.get("worker_state"))
    simulation_sync = _text(ledger.get("simulation_sync_status"))
    htvs_summary = Path(settings.results_storage_path) / resolved_job_id / "htvs_summary.json"
    result_template = Path(settings.results_storage_path) / resolved_job_id / "htvs_summary.json"

    success = worker_state == "completed_fail_closed" and simulation_sync == "completed"
    return {
        "summary": {
            "packet_type": "tier_alpha_adrb2_dispatch_smoke",
            "status": "tier_alpha_adrb2_dispatch_smoke_pass" if success else "tier_alpha_adrb2_dispatch_smoke_failed",
            "evidence_mode": "live_job" if success else "live_job_failed",
            "api_validated_runner_enabled": settings.api_validated_runner_enabled,
            "workspace": str(workspace_path.relative_to(ROOT) if workspace_path.is_relative_to(ROOT) else workspace_path),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "job_id": resolved_job_id,
        "ledger_worker_state": worker_state or "not_started_fail_closed",
        "simulation_sync_status": simulation_sync,
        "dispatch_outcome": dispatch_outcome,
        "worker_ran": worker_ran,
        "sqlite_job_status": sqlite_status,
        "worker_error": last_error,
        "jobs_dir": str(jobs_dir.relative_to(ROOT) if jobs_dir.is_relative_to(ROOT) else jobs_dir),
        "htvs_summary_exists": htvs_summary.exists(),
        "result_file": str(result_template) if result_template.exists() else "",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Tier α ADRB2 dispatch smoke with API_VALIDATED_RUNNER_ENABLED=1.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--job-id", default="")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = run_tier_alpha_adrb2_dispatch_smoke(
        workspace=args.workspace,
        job_id=_text(args.job_id) or None,
        timeout_seconds=max(30, int(args.timeout_seconds)),
    )
    out = ROOT / args.out_json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["summary"]["status"], "job_id": payload["job_id"], "out_json": str(out)}))
    if payload["summary"]["status"] != "tier_alpha_adrb2_dispatch_smoke_pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
