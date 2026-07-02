#!/usr/bin/env python3
"""Gate restricted-scope unattended API execution readiness (Tier α)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_E2E_JSON = "runs/api_docking_dispatch_e2e_evidence_current.json"
DEFAULT_PROMOTION_JSON = "runs/api_runner_profile_promotion_readiness_current.json"
DEFAULT_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_ARCH_JSON = "runs/architecture_validation_package_report_current.json"
DEFAULT_SMOKE_JSON = "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
DEFAULT_OUT_JSON = "runs/restricted_unattended_execution_readiness_current.json"

CLAIM_BOUNDARY = (
    "Restricted unattended execution readiness only; it aggregates local wiring, profile promotion, "
    "delivery verdict, and architecture validation signals for gpcr/ion_channel/kinase scope. "
    "It does not enable execution globally, widen scope, or mutate external state."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _status_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    direct = smoke.get("status_payload")
    if isinstance(direct, dict):
        return direct
    status_json = _text(smoke.get("status_json"))
    return _read_json(status_json) if status_json else {}


def _ledger_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    direct = smoke.get("ledger_payload")
    if isinstance(direct, dict):
        return direct
    jobs_dir = _text(smoke.get("jobs_dir"))
    job_id = _text(smoke.get("job_id"))
    if not jobs_dir or not job_id:
        return {}
    return _read_json(_resolve(jobs_dir) / f"{job_id}.json")


def _runner_execution_from_smoke(smoke: dict[str, Any]) -> dict[str, Any]:
    direct = smoke.get("runner_execution_payload")
    if isinstance(direct, dict):
        return direct
    runner_execution = _text(smoke.get("runner_execution"))
    if not runner_execution:
        runner_execution = _text(_status_from_smoke(smoke).get("runner_execution"))
    return _read_json(runner_execution) if runner_execution else {}


def _recovered_completed_runtime_smoke(smoke: dict[str, Any], smoke_summary: dict[str, Any]) -> bool:
    status = _status_from_smoke(smoke)
    ledger = _ledger_from_smoke(smoke)
    runner_execution = _runner_execution_from_smoke(smoke)
    runner_execution_ok = (
        smoke.get("runner_execution_ok") is True
        or (
            runner_execution.get("ok") is True
            and _int(runner_execution.get("returncode")) == 0
            and runner_execution.get("timed_out") is not True
        )
    )
    ledger_worker_state = _text(
        ledger.get("worker_state") or ledger.get("queue_status") or ledger.get("status")
    )
    ledger_progress_state = _text(ledger.get("progress_state") or ledger.get("current_step"))
    return (
        smoke_summary.get("status") == "tier_alpha_adrb2_dispatch_smoke_pass"
        and _text(smoke_summary.get("evidence_mode")) == "live_job_recovered_from_completed_artifacts"
        and smoke.get("recovered_from_completed_artifacts") is True
        and bool(smoke_summary.get("api_validated_runner_enabled"))
        and smoke.get("result_manifest_signature_verified") is True
        and _text(smoke.get("result_manifest_status")) == "completed"
        and runner_execution_ok
        and smoke.get("worker_dispatch_enqueued") is True
        and smoke.get("worker_ran") is True
        and _text(smoke.get("sqlite_job_status")) == "completed"
        and _text(status.get("status")) == "completed"
        and ledger_worker_state == "completed_fail_closed"
        and ledger_progress_state == "worker_dispatch_completed"
    )


def build_restricted_unattended_execution_readiness(
    *,
    e2e_json: str = DEFAULT_E2E_JSON,
    promotion_json: str = DEFAULT_PROMOTION_JSON,
    verdict_json: str = DEFAULT_VERDICT_JSON,
    arch_json: str = DEFAULT_ARCH_JSON,
    smoke_json: str = DEFAULT_SMOKE_JSON,
) -> dict[str, Any]:
    e2e = _read_json(e2e_json)
    e2e_summary = _summary(e2e)
    promotion = _summary(_read_json(promotion_json))
    verdict = _summary(_read_json(verdict_json))
    arch = _summary(_read_json(arch_json))
    smoke = _read_json(smoke_json)
    smoke_summary = _summary(smoke)

    runtime_runner_enabled = os.environ.get("API_VALIDATED_RUNNER_ENABLED", "0").strip() in {"1", "true", "yes"}
    smoke_runtime = (
        smoke_summary.get("status") == "tier_alpha_adrb2_dispatch_smoke_pass"
        and smoke.get("ledger_worker_state") == "completed_fail_closed"
        and bool(smoke_summary.get("api_validated_runner_enabled"))
    ) or _recovered_completed_runtime_smoke(smoke, smoke_summary)

    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "gate_id": "api_dispatch_e2e_wiring",
            "status": "pass" if e2e_summary.get("wiring_ready") is True else "blocked",
            "observed": f"e2e_status={e2e_summary.get('status')};ledger={e2e.get('ledger_worker_state')}",
            "required": "api_docking_dispatch_e2e_ready with completed_fail_closed ledger state",
        }
    )
    rows.append(
        {
            "gate_id": "runner_profile_promotion",
            "status": "pass" if _text(promotion.get("status")) == "api_runner_profile_promotion_ready" else "blocked",
            "observed": _text(promotion.get("status")),
            "required": "api_runner_profile_promotion_ready",
        }
    )
    rows.append(
        {
            "gate_id": "local_delivery_verdict",
            "status": "pass" if _bool(verdict.get("delivery_ready")) else "blocked",
            "observed": _text(verdict.get("verdict")),
            "required": "delivery_ready=true",
        }
    )
    package_a = _bool(arch.get("package_a_complete"))
    rows.append(
        {
            "gate_id": "architecture_validation_package_a",
            "status": "pass" if package_a else "blocked",
            "observed": f"package_a_complete={arch.get('package_a_complete')}",
            "required": "package_a_complete=true",
        }
    )
    rows.append(
        {
            "gate_id": "runtime_api_validated_runner_enabled",
            "status": "pass" if (runtime_runner_enabled or smoke_runtime) else "operator_pending",
            "observed": (
                f"API_VALIDATED_RUNNER_ENABLED={os.environ.get('API_VALIDATED_RUNNER_ENABLED', '0')};"
                f"smoke_runtime={smoke_runtime}"
            ),
            "required": "operator sets API_VALIDATED_RUNNER_ENABLED=1 in deploy runtime or passes Tier α smoke",
        }
    )

    hard_blocked = [row for row in rows if row["status"] == "blocked"]
    wiring_ready = e2e_summary.get("wiring_ready") is True and not hard_blocked
    runtime_live = wiring_ready and (runtime_runner_enabled or smoke_runtime)

    return {
        "summary": {
            "packet_type": "restricted_unattended_execution_readiness",
            "status": (
                "restricted_unattended_execution_runtime_ready"
                if runtime_live
                else "restricted_unattended_execution_wiring_ready"
                if wiring_ready
                else "blocked_restricted_unattended_execution_readiness"
            ),
            "restricted_unattended_execution_ready": wiring_ready,
            "restricted_unattended_execution_runtime_ready": runtime_live,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "general_platform_claim_allowed": False,
            "execution_enabled_at_runtime": runtime_runner_enabled or smoke_runtime,
            "tier_alpha_smoke_runtime_verified": smoke_runtime,
            "claim_promotion_allowed": False,
            "gate_count": len(rows),
            "blocked_gate_count": len(hard_blocked),
            "operator_pending_gate_count": sum(1 for row in rows if row["status"] == "operator_pending"),
            "claim_boundary": CLAIM_BOUNDARY,
            "next_action": (
                "Set API_VALIDATED_RUNNER_ENABLED=1 in deploy and run live ADRB2 dispatch smoke."
                if wiring_ready and not (runtime_runner_enabled or smoke_runtime)
                else "Repair blocked gates before unattended execution promotion."
                if hard_blocked
                else "Maintain restricted-scope dispatch SLA and profile rollback path."
            ),
        },
        "rows": rows,
        "tier_alpha_smoke_artifact": smoke_json if smoke else "",
        "e2e_ledger_worker_state": e2e.get("ledger_worker_state"),
        "e2e_evidence_mode": e2e_summary.get("evidence_mode"),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build restricted unattended execution readiness gate.")
    parser.add_argument("--e2e-json", default=DEFAULT_E2E_JSON)
    parser.add_argument("--promotion-json", default=DEFAULT_PROMOTION_JSON)
    parser.add_argument("--verdict-json", default=DEFAULT_VERDICT_JSON)
    parser.add_argument("--arch-json", default=DEFAULT_ARCH_JSON)
    parser.add_argument("--smoke-json", default=DEFAULT_SMOKE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_restricted_unattended_execution_readiness(
        e2e_json=args.e2e_json,
        promotion_json=args.promotion_json,
        verdict_json=args.verdict_json,
        arch_json=args.arch_json,
        smoke_json=args.smoke_json,
    )
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
