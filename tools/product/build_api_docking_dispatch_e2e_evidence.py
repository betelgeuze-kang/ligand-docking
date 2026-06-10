#!/usr/bin/env python3
"""Audit API docking dispatch E2E wiring evidence (Package A A-40)."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROFILES_DIR = "config/api_validated_runner_profiles"
DEFAULT_PROMOTION_JSON = "runs/api_runner_profile_promotion_readiness_current.json"
DEFAULT_JOBS_DIR = "runs/product_docking_jobs"
DEFAULT_SMOKE_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_OUT_JSON = "runs/api_docking_dispatch_e2e_evidence_current.json"
DEFAULT_SMOKE_PRESET = "config/ligand_htvs_api_dispatch_smoke_v1.json"

CLAIM_BOUNDARY = (
    "API docking dispatch E2E evidence only; it audits runner profiles, dispatch infrastructure, and "
    "ledger sync wiring. Synthetic in-process ledger sync proves code path only. It does not submit "
    "live docking jobs, enable global execution, or mutate external state."
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _enabled_profiles(profiles_dir: Path) -> list[str]:
    enabled: list[str] = []
    if not profiles_dir.is_dir():
        return enabled
    for path in sorted(profiles_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        payload = _read_json(path)
        if payload.get("enabled") is True:
            enabled.append(path.stem)
    return enabled


def _compose_services(compose_path: Path) -> list[str]:
    if not compose_path.is_file():
        return []
    text = compose_path.read_text(encoding="utf-8", errors="ignore")
    services: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and not stripped.startswith("#") and line.startswith("  ") and not line.startswith("    "):
            name = stripped[:-1]
            if name not in {"services", "volumes", "networks", "build", "environment", "command", "depends_on", "ports", "restart", "image"}:
                services.append(name)
    return [item for item in services if item in {"api-server", "api-worker", "api-docking-dispatch"}]


def _scan_live_ledger(jobs_dir: Path) -> dict[str, Any]:
    if not jobs_dir.is_dir():
        return {"live_job_found": False}
    best: dict[str, Any] = {"live_job_found": False}
    for path in sorted(jobs_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        worker_state = _text(record.get("worker_state"))
        if worker_state == "completed_fail_closed":
            return {
                "live_job_found": True,
                "job_id": _text(record.get("job_id") or path.stem),
                "ledger_worker_state": worker_state,
                "simulation_sync_status": _text(record.get("simulation_sync_status")),
                "worker_dispatch_enqueued": record.get("worker_dispatch_enqueued"),
            }
        if worker_state and not best.get("live_job_found"):
            best = {
                "live_job_found": True,
                "job_id": _text(record.get("job_id") or path.stem),
                "ledger_worker_state": worker_state,
                "simulation_sync_status": _text(record.get("simulation_sync_status")),
                "worker_dispatch_enqueued": record.get("worker_dispatch_enqueued"),
            }
    return best


def _synthetic_ledger_sync_proof() -> dict[str, Any]:
    from api.docking_dispatch import sync_ledger_from_simulation_result

    with tempfile.TemporaryDirectory() as tmp:
        jobs_dir = Path(tmp) / "jobs"
        jobs_dir.mkdir()
        job_id = "e2e-wiring-proof"
        record = {"job_id": job_id, "status": "accepted_fail_closed", "queue_status": "queued_fail_closed"}
        (jobs_dir / f"{job_id}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        sync = sync_ledger_from_simulation_result(
            jobs_dir,
            job_id,
            status="completed",
            result_file=str(Path(tmp) / "result.json"),
            worker_id="e2e-evidence-builder",
        )
        updated = json.loads((jobs_dir / f"{job_id}.json").read_text(encoding="utf-8"))
    ok = (
        sync.get("synced") is True
        and _text(updated.get("worker_state")) == "completed_fail_closed"
        and _text(updated.get("simulation_sync_status")) == "completed"
    )
    return {
        "synthetic_sync_pass": ok,
        "ledger_worker_state": _text(updated.get("worker_state")) if ok else "failed_wiring_proof",
        "simulation_sync_status": _text(updated.get("simulation_sync_status")) if ok else "failed",
    }


def build_api_docking_dispatch_e2e_evidence(
    *,
    profiles_dir: str = DEFAULT_PROFILES_DIR,
    promotion_json: str = DEFAULT_PROMOTION_JSON,
    jobs_dir: str = DEFAULT_JOBS_DIR,
    smoke_json: str = DEFAULT_SMOKE_JSON,
    smoke_preset: str = DEFAULT_SMOKE_PRESET,
) -> dict[str, Any]:
    profiles_path = _resolve(profiles_dir)
    promotion = _summary(_read_json(promotion_json))
    smoke = _read_json(smoke_json)
    smoke_summary = _summary(smoke)
    enabled = _enabled_profiles(profiles_path)
    compose_path = _resolve("deploy/docker-compose.product.yml")
    compose_services = _compose_services(compose_path)
    synthetic = _synthetic_ledger_sync_proof()
    smoke_jobs_dir = _text(smoke.get("jobs_dir")) or jobs_dir
    live = _scan_live_ledger(_resolve(smoke_jobs_dir))
    if _text(smoke_summary.get("evidence_mode")) == "live_job" and _text(smoke.get("ledger_worker_state")) == "completed_fail_closed":
        live = {
            "live_job_found": True,
            "job_id": _text(smoke.get("job_id")),
            "ledger_worker_state": _text(smoke.get("ledger_worker_state")),
            "simulation_sync_status": _text(smoke.get("simulation_sync_status")),
            "source": "tier_alpha_adrb2_dispatch_smoke",
        }

    checks: list[dict[str, Any]] = []
    promotion_ready = _text(promotion.get("status")) == "api_runner_profile_promotion_ready"
    checks.append(
        {
            "check_id": "runner_profile_promotion_ready",
            "status": "pass" if promotion_ready else "blocked",
            "detail": f"status={promotion.get('status')};blocked={promotion.get('blocked_profile_count')}",
        }
    )
    checks.append(
        {
            "check_id": "enabled_runner_profiles",
            "status": "pass" if enabled else "blocked",
            "detail": f"enabled_profiles={','.join(enabled) or 'none'}",
        }
    )
    dispatch_script = _resolve("tools/run_api_docking_dispatch_worker.py").is_file()
    worker_script = _resolve("tools/run_api_simulation_worker.py").is_file()
    checks.append(
        {
            "check_id": "dispatch_worker_scripts_present",
            "status": "pass" if dispatch_script and worker_script else "blocked",
            "detail": f"dispatch={dispatch_script};worker={worker_script}",
        }
    )
    compose_ok = set(compose_services) >= {"api-server", "api-worker", "api-docking-dispatch"}
    checks.append(
        {
            "check_id": "docker_compose_three_process_stack",
            "status": "pass" if compose_ok else "blocked",
            "detail": f"services={','.join(compose_services)}",
        }
    )
    checks.append(
        {
            "check_id": "dispatch_smoke_preset_present",
            "status": "pass" if _resolve(smoke_preset).is_file() else "blocked",
            "detail": smoke_preset,
        }
    )
    checks.append(
        {
            "check_id": "synthetic_ledger_sync_proof",
            "status": "pass" if synthetic.get("synthetic_sync_pass") else "blocked",
            "detail": f"worker_state={synthetic.get('ledger_worker_state')}",
        }
    )

    wiring_ready = all(item["status"] == "pass" for item in checks)
    evidence_mode = "live_job" if live.get("live_job_found") and _text(live.get("ledger_worker_state")) == "completed_fail_closed" else "synthetic_wiring_proof"
    if evidence_mode == "live_job":
        ledger_worker_state = _text(live.get("ledger_worker_state"))
        simulation_sync_status = _text(live.get("simulation_sync_status"))
    elif wiring_ready and synthetic.get("synthetic_sync_pass"):
        ledger_worker_state = "completed_fail_closed"
        simulation_sync_status = "completed"
    else:
        ledger_worker_state = "blocked_wiring_not_ready"
        simulation_sync_status = "blocked"

    blocked = [item for item in checks if item["status"] != "pass"]
    return {
        "summary": {
            "packet_type": "api_docking_dispatch_e2e_evidence",
            "status": "api_docking_dispatch_e2e_ready" if wiring_ready else "blocked_api_docking_dispatch_e2e_evidence",
            "wiring_ready": wiring_ready,
            "evidence_mode": evidence_mode,
            "enabled_runner_profile_count": len(enabled),
            "enabled_runner_profiles": enabled,
            "check_count": len(checks),
            "pass_count": sum(1 for item in checks if item["status"] == "pass"),
            "blocked_count": len(blocked),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "ledger_worker_state": ledger_worker_state,
        "simulation_sync_status": simulation_sync_status,
        "live_ledger_scan": live,
        "tier_alpha_smoke_artifact": smoke_json if smoke else "",
        "tier_alpha_smoke_status": _text(smoke_summary.get("status")),
        "synthetic_ledger_sync": synthetic,
        "checks": checks,
        "next_action": (
            "Deploy api-server, api-worker, and api-docking-dispatch with API_VALIDATED_RUNNER_ENABLED=1 and run ADRB2 dispatch smoke."
            if wiring_ready and evidence_mode != "live_job"
            else "Repair blocked wiring checks before claiming API dispatch E2E readiness."
            if not wiring_ready
            else "Maintain live dispatch smoke on restricted scope targets."
        ),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build API docking dispatch E2E wiring evidence.")
    parser.add_argument("--profiles-dir", default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--jobs-dir", default=DEFAULT_JOBS_DIR)
    parser.add_argument("--smoke-json", default=DEFAULT_SMOKE_JSON)
    parser.add_argument("--smoke-preset", default=DEFAULT_SMOKE_PRESET)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_api_docking_dispatch_e2e_evidence(
        profiles_dir=args.profiles_dir,
        promotion_json=args.promotion_json,
        jobs_dir=args.jobs_dir,
        smoke_json=args.smoke_json,
        smoke_preset=args.smoke_preset,
    )
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
