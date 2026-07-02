#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SERVICE_BOUNDARY_JSON = "runs/product_service_boundary_contract_current.json"
DEFAULT_SECURITY_DEPLOYMENT_JSON = "runs/product_security_deployment_contract_current.json"
DEFAULT_JOB_ORCHESTRATION_JSON = "runs/product_job_orchestration_contract_current.json"
DEFAULT_ROLLOUT_READINESS_JSON = "runs/product_rollout_execution_readiness_current.json"
DEFAULT_ROLLOUT_SMOKE_RECEIPT_JSON = "runs/product_rollout_execution_smoke_receipt_current.json"
DEFAULT_LICENSE_AUDIT_JSON = "runs/self_hosted_license_distribution_audit_current.json"
DEFAULT_LEDGER_PRIVACY_JSON = "runs/product_ledger_privacy_scan_current.json"
DEFAULT_API_CUSTOMER_FLOW_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_SUPPORT_BUNDLE_JSON = "runs/support_bundle_current.json"
DEFAULT_PRODUCT_STAGE_ROADMAP_MD = "docs/product_stage_and_roadmap_2026_06_30.md"
DEFAULT_TARGET_ARCHITECTURE_MD = "docs/target_bioscience_architecture.md"
DEFAULT_OUT_JSON = "runs/enterprise_on_prem_readiness_gate_current.json"
DEFAULT_OUT_CSV = "runs/enterprise_on_prem_readiness_gate_current.csv"
DEFAULT_OUT_MD = "runs/enterprise_on_prem_readiness_gate_current.md"

CLAIM_BOUNDARY = (
    "Enterprise/on-prem readiness gate only; aggregates local readiness artifacts and target docs into a "
    "non-promoting operator work order. It does not start services, run docking, build images, deploy, "
    "upload, email, delete, commit, push, submit external jobs, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _artifact(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _read_text(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_true(value: Any) -> bool:
    return value is True


def _metric(label: str, value: Any) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    else:
        rendered = _text(value)
    return f"{label}={rendered}" if rendered else ""


def _join(*items: str) -> str:
    return ";".join(item for item in items if item)


def _doc_has(text: str, *phrases: str) -> bool:
    lowered = text.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


def _row(
    *,
    control_id: str,
    title: str,
    status: str,
    ready: bool,
    evidence_artifacts: list[str],
    evidence: str,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "control_id": control_id,
        "title": title,
        "status": status,
        "ready": ready,
        "evidence_artifacts": evidence_artifacts,
        "evidence": evidence,
        "blocker": "" if ready else blocker,
        "next_action": next_action,
        "claim_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _status_ready(summary: dict[str, Any], expected: str) -> bool:
    return _text(summary.get("status")) == expected


def build_enterprise_on_prem_readiness_gate(
    *,
    root: Path = ROOT,
    service_boundary_json: str | Path = DEFAULT_SERVICE_BOUNDARY_JSON,
    security_deployment_json: str | Path = DEFAULT_SECURITY_DEPLOYMENT_JSON,
    job_orchestration_json: str | Path = DEFAULT_JOB_ORCHESTRATION_JSON,
    rollout_readiness_json: str | Path = DEFAULT_ROLLOUT_READINESS_JSON,
    rollout_smoke_receipt_json: str | Path = DEFAULT_ROLLOUT_SMOKE_RECEIPT_JSON,
    license_audit_json: str | Path = DEFAULT_LICENSE_AUDIT_JSON,
    ledger_privacy_json: str | Path = DEFAULT_LEDGER_PRIVACY_JSON,
    api_customer_flow_json: str | Path = DEFAULT_API_CUSTOMER_FLOW_JSON,
    support_bundle_json: str | Path = DEFAULT_SUPPORT_BUNDLE_JSON,
    product_stage_roadmap_md: str | Path = DEFAULT_PRODUCT_STAGE_ROADMAP_MD,
    target_architecture_md: str | Path = DEFAULT_TARGET_ARCHITECTURE_MD,
) -> dict[str, Any]:
    root = Path(root)
    service = _summary(_read_json(service_boundary_json, root=root))
    security = _summary(_read_json(security_deployment_json, root=root))
    jobs = _summary(_read_json(job_orchestration_json, root=root))
    rollout = _summary(_read_json(rollout_readiness_json, root=root))
    rollout_smoke = _summary(_read_json(rollout_smoke_receipt_json, root=root))
    license_audit = _summary(_read_json(license_audit_json, root=root))
    ledger_privacy = _summary(_read_json(ledger_privacy_json, root=root))
    api_flow = _summary(_read_json(api_customer_flow_json, root=root))
    support_bundle = _summary(_read_json(support_bundle_json, root=root))
    roadmap_text = _read_text(product_stage_roadmap_md, root=root)
    architecture_text = _read_text(target_architecture_md, root=root)

    service_ready = (
        _status_ready(service, "product_service_boundary_contract_ready")
        and _bool_true(service.get("service_boundary_ready"))
        and _bool_true(service.get("console_script_ready"))
        and _int(service.get("missing_api_route_count")) == 0
        and _int(service.get("missing_cli_command_count")) == 0
    )
    oidc_rbac_ready = (
        _bool_true(security.get("oidc_ready"))
        and _bool_true(security.get("rbac_ready"))
        and _bool_true(security.get("tenant_isolation_ready"))
    )
    tls_ready = (
        _bool_true(security.get("hosted_external_exposure_allowed"))
        and _bool_true(security.get("tls_termination_operator_verified"))
        and _bool_true(rollout_smoke.get("ingress_certificate_verified_live"))
        and _bool_true(rollout_smoke.get("rollout_execution_smoke_receipt_ready"))
    )
    durable_queue_ready = (
        _status_ready(jobs, "product_job_orchestration_contract_ready")
        and _bool_true(jobs.get("product_job_orchestration_contract_ready"))
        and _bool_true(jobs.get("worker_lease_heartbeat_ready"))
        and _bool_true(jobs.get("retry_child_attempt_created"))
        and _bool_true(jobs.get("idempotency_preserved"))
        and _bool_true(jobs.get("retryable_failure_resume_ready"))
    )
    object_storage_ready = _bool_true(security.get("object_storage_ready")) or _bool_true(
        rollout.get("object_storage_ready")
    )
    gpu_scheduler_ready = _bool_true(rollout.get("gpu_scheduler_ready")) or _bool_true(
        jobs.get("gpu_scheduler_ready")
    )
    audit_provenance_ready = (
        _bool_true(security.get("audit_log_ready"))
        and _bool_true(security.get("metrics_endpoint_ready"))
        and _bool_true(ledger_privacy.get("ledger_privacy_scan_ready"))
        and _bool_true(api_flow.get("result_manifest_signature_verified"))
        and (
            _bool_true(api_flow.get("trace_correlation_ready"))
            or _bool_true(security.get("distributed_tracing_ready"))
        )
    )
    license_ready = (
        _status_ready(license_audit, "self_hosted_license_distribution_audit_recorded")
        and _int(license_audit.get("hard_blocker_count")) == 0
        and _bool_true(license_audit.get("third_party_license_review_gate_ready"))
    )
    support_bundle_ready = (
        _status_ready(support_bundle, "support_bundle_ready")
        and _bool_true(support_bundle.get("support_bundle_ready"))
        and _bool_true(support_bundle.get("customer_safe_bundle_ready"))
    )
    rollback_retry_ready = (
        _bool_true(security.get("rollback_ready"))
        and _bool_true(rollout_smoke.get("rollout_execution_smoke_receipt_ready"))
        and _bool_true(rollout_smoke.get("rollout_executed"))
        and durable_queue_ready
    )

    rows = [
        _row(
            control_id="versioned_api_sdk_cli",
            title="Versioned API/SDK/CLI surface",
            status="enterprise_control_ready" if service_ready else "blocked_enterprise_control",
            ready=service_ready,
            evidence_artifacts=[_artifact(service_boundary_json, root=root)],
            evidence=_join(
                _metric("service_boundary_ready", _bool_true(service.get("service_boundary_ready"))),
                _metric("api_routes", _int(service.get("api_route_count"))),
                _metric("cli_commands", _int(service.get("cli_command_count"))),
                _metric("console_script_ready", _bool_true(service.get("console_script_ready"))),
            ),
            blocker="versioned_api_sdk_cli_contract_missing",
            next_action="Keep API/CLI compatibility checks in the enterprise release ledger.",
        ),
        _row(
            control_id="oidc_rbac_tenant_isolation",
            title="OIDC/RBAC and tenant isolation",
            status="enterprise_control_ready" if oidc_rbac_ready else "blocked_oidc_rbac_not_verified",
            ready=oidc_rbac_ready,
            evidence_artifacts=[_artifact(security_deployment_json, root=root)],
            evidence=_join(
                _metric("auth_ready", _bool_true(security.get("auth_ready"))),
                _metric("tenant_isolation_ready", _bool_true(security.get("tenant_isolation_ready"))),
                _metric("oidc_ready", _bool_true(security.get("oidc_ready"))),
                _metric("rbac_ready", _bool_true(security.get("rbac_ready"))),
            ),
            blocker="oidc_rbac_claim_grade_evidence_missing",
            next_action="Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts.",
        ),
        _row(
            control_id="tls_hosted_exposure",
            title="TLS and hosted exposure approval",
            status="enterprise_control_ready" if tls_ready else "blocked_tls_or_exposure_approval_missing",
            ready=tls_ready,
            evidence_artifacts=[
                _artifact(security_deployment_json, root=root),
                _artifact(rollout_smoke_receipt_json, root=root),
            ],
            evidence=_join(
                _metric(
                    "hosted_external_exposure_allowed",
                    _bool_true(security.get("hosted_external_exposure_allowed")),
                ),
                _metric(
                    "tls_operator_verified",
                    _bool_true(security.get("tls_termination_operator_verified")),
                ),
                _metric(
                    "live_certificate_verified",
                    _bool_true(rollout_smoke.get("ingress_certificate_verified_live")),
                ),
                _metric(
                    "rollout_smoke_ready",
                    _bool_true(rollout_smoke.get("rollout_execution_smoke_receipt_ready")),
                ),
            ),
            blocker="hosted_exposure_or_tls_operator_verification_missing",
            next_action=_text(security.get("hosted_deployment_next_stage_required"))
            or "Attach operator-approved hosted exposure and TLS verification receipts.",
        ),
        _row(
            control_id="durable_queue_retry_idempotency",
            title="Durable queue, retry, and idempotency",
            status="enterprise_control_ready" if durable_queue_ready else "blocked_queue_retry_evidence_missing",
            ready=durable_queue_ready,
            evidence_artifacts=[_artifact(job_orchestration_json, root=root)],
            evidence=_join(
                _metric("worker_lease_heartbeat_ready", _bool_true(jobs.get("worker_lease_heartbeat_ready"))),
                _metric("retry_child_attempt_created", _bool_true(jobs.get("retry_child_attempt_created"))),
                _metric("idempotency_preserved", _bool_true(jobs.get("idempotency_preserved"))),
                _metric("retry_resume_ready", _bool_true(jobs.get("retryable_failure_resume_ready"))),
            ),
            blocker="durable_queue_retry_idempotency_contract_missing",
            next_action="Keep durable queue and retry receipts attached to enterprise readiness.",
        ),
        _row(
            control_id="object_storage_artifact_plane",
            title="Object storage artifact plane",
            status="enterprise_control_ready" if object_storage_ready else "blocked_object_storage_contract_missing",
            ready=object_storage_ready,
            evidence_artifacts=[_artifact(target_architecture_md, root=root)],
            evidence=_join(
                _metric("target_architecture_mentions_object_storage", _doc_has(architecture_text, "object storage")),
                _metric("object_storage_ready", object_storage_ready),
            ),
            blocker="object_storage_claim_grade_evidence_missing",
            next_action="Add object storage adapter, signed artifact location policy, and restore/retention receipts.",
        ),
        _row(
            control_id="gpu_scheduler_resource_quota",
            title="GPU scheduler and resource quotas",
            status="enterprise_control_ready" if gpu_scheduler_ready else "blocked_gpu_scheduler_contract_missing",
            ready=gpu_scheduler_ready,
            evidence_artifacts=[_artifact(target_architecture_md, root=root)],
            evidence=_join(
                _metric("target_architecture_mentions_gpu_scheduler", _doc_has(architecture_text, "gpu scheduler")),
                _metric("gpu_scheduler_ready", gpu_scheduler_ready),
            ),
            blocker="gpu_scheduler_claim_grade_evidence_missing",
            next_action="Add GPU scheduler, quota, admission-control, and recovery receipts before enterprise claims.",
        ),
        _row(
            control_id="audit_provenance_metrics_tracing",
            title="Audit logs, provenance, metrics, and tracing",
            status="enterprise_control_ready" if audit_provenance_ready else "blocked_tracing_receipt_missing",
            ready=audit_provenance_ready,
            evidence_artifacts=[
                _artifact(security_deployment_json, root=root),
                _artifact(ledger_privacy_json, root=root),
                _artifact(api_customer_flow_json, root=root),
            ],
            evidence=_join(
                _metric("audit_log_ready", _bool_true(security.get("audit_log_ready"))),
                _metric("metrics_endpoint_ready", _bool_true(security.get("metrics_endpoint_ready"))),
                _metric("privacy_scan_ready", _bool_true(ledger_privacy.get("ledger_privacy_scan_ready"))),
                _metric(
                    "result_manifest_signature_verified",
                    _bool_true(api_flow.get("result_manifest_signature_verified")),
                ),
                _metric("trace_correlation_ready", _bool_true(api_flow.get("trace_correlation_ready"))),
            ),
            blocker="metrics_tracing_claim_grade_evidence_missing",
            next_action="Attach trace-correlation or distributed-tracing evidence that links API, queue, GPU worker, and bundle.",
        ),
        _row(
            control_id="license_control",
            title="License control for self-hosted distribution",
            status="enterprise_control_ready" if license_ready else "blocked_license_control_missing",
            ready=license_ready,
            evidence_artifacts=[_artifact(license_audit_json, root=root)],
            evidence=_join(
                _metric("license_status", license_audit.get("status")),
                _metric("hard_blockers", _int(license_audit.get("hard_blocker_count"))),
                _metric(
                    "third_party_review_ready",
                    _bool_true(license_audit.get("third_party_license_review_gate_ready")),
                ),
                _metric("spdx", license_audit.get("spdx_license_id")),
            ),
            blocker="self_hosted_license_control_evidence_missing",
            next_action="Keep license and third-party review receipts attached; legal approval remains outside this gate.",
        ),
        _row(
            control_id="support_bundle_recovery_drill",
            title="Support bundle and recovery drill",
            status="enterprise_control_ready" if support_bundle_ready else "blocked_support_bundle_receipt_missing",
            ready=support_bundle_ready,
            evidence_artifacts=[_artifact(support_bundle_json, root=root)],
            evidence=_join(
                _metric("support_bundle_artifact_present", bool(support_bundle)),
                _metric("support_bundle_ready", _bool_true(support_bundle.get("support_bundle_ready"))),
                _metric(
                    "customer_safe_bundle_ready",
                    _bool_true(support_bundle.get("customer_safe_bundle_ready")),
                ),
            ),
            blocker="support_bundle_and_recovery_drill_missing",
            next_action="Add redacted support bundle, recovery drill, and incident handoff receipts.",
        ),
        _row(
            control_id="rollback_retry_idempotency",
            title="Rollback, retry, and idempotency drill",
            status="enterprise_control_ready" if rollback_retry_ready else "blocked_rollback_drill_not_enterprise_complete",
            ready=rollback_retry_ready,
            evidence_artifacts=[
                _artifact(security_deployment_json, root=root),
                _artifact(job_orchestration_json, root=root),
                _artifact(rollout_smoke_receipt_json, root=root),
            ],
            evidence=_join(
                _metric("rollback_ready", _bool_true(security.get("rollback_ready"))),
                _metric("rollout_executed", _bool_true(rollout_smoke.get("rollout_executed"))),
                _metric("durable_queue_ready", durable_queue_ready),
                _metric("rollout_target_environment", rollout_smoke.get("target_environment")),
            ),
            blocker="rollback_retry_drill_evidence_missing",
            next_action="Attach rollback activation and retry/idempotency drill receipts for the target deployment mode.",
        ),
    ]

    ready_count = sum(1 for row in rows if row["ready"])
    blocker_rows = [row for row in rows if not row["ready"]]
    blocker_count = len(blocker_rows)
    enterprise_ready = blocker_count == 0
    first_blocker = blocker_rows[0] if blocker_rows else {}
    roadmap_phase_present = _doc_has(roadmap_text, "phase 6 - enterprise platform")
    target_architecture_present = _doc_has(
        architecture_text,
        "postgresql",
        "durable queue",
        "gpu scheduler",
        "object storage",
        "oidc/rbac",
        "audit logs",
        "retry/restart",
    )
    source_external_state_mutated_count = sum(
        1
        for summary in [
            service,
            security,
            jobs,
            rollout,
            rollout_smoke,
            license_audit,
            ledger_privacy,
            api_flow,
            support_bundle,
        ]
        if _bool_true(summary.get("external_state_mutated"))
    )
    summary = {
        "packet_type": "enterprise_on_prem_readiness_gate",
        "status": (
            "enterprise_on_prem_readiness_gate_ready"
            if enterprise_ready
            else "blocked_enterprise_on_prem_readiness_gate"
        ),
        "enterprise_on_prem_ready": enterprise_ready,
        "enterprise_platform_claim_allowed": False,
        "on_prem_claim_allowed": False,
        "general_platform_claim_allowed": False,
        "control_count": len(rows),
        "ready_control_count": ready_count,
        "blocked_control_count": blocker_count,
        "ready_control_ids": [row["control_id"] for row in rows if row["ready"]],
        "blocked_control_ids": [row["control_id"] for row in blocker_rows],
        "primary_blocker_id": _text(first_blocker.get("control_id")),
        "primary_blocker": _text(first_blocker.get("blocker")),
        "next_required_step": _text(first_blocker.get("next_action"))
        or "No enterprise/on-prem blockers remain.",
        "roadmap_enterprise_phase_present": roadmap_phase_present,
        "target_architecture_enterprise_controls_present": target_architecture_present,
        "source_external_state_mutated_count": source_external_state_mutated_count,
        "operator_runbook_dependency_remaining": not enterprise_ready,
        "hosted_external_exposure_allowed": _bool_true(security.get("hosted_external_exposure_allowed")),
        "tls_termination_operator_verified": _bool_true(
            security.get("tls_termination_operator_verified")
        ),
        "live_tls_certificate_receipt_ready": _bool_true(
            rollout_smoke.get("ingress_certificate_verified_live")
        ),
        "oidc_rbac_ready": oidc_rbac_ready,
        "durable_queue_retry_idempotency_ready": durable_queue_ready,
        "object_storage_ready": object_storage_ready,
        "gpu_scheduler_ready": gpu_scheduler_ready,
        "audit_provenance_metrics_tracing_ready": audit_provenance_ready,
        "license_control_ready": license_ready,
        "support_bundle_recovery_drill_ready": support_bundle_ready,
        "rollback_retry_idempotency_ready": rollback_retry_ready,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Enterprise On-Prem Readiness Gate",
        "",
        f"- status: `{s['status']}`",
        f"- enterprise_on_prem_ready: `{s['enterprise_on_prem_ready']}`",
        f"- ready_control_count: `{s['ready_control_count']}`",
        f"- blocked_control_count: `{s['blocked_control_count']}`",
        f"- primary_blocker_id: `{s['primary_blocker_id']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "| control | status | ready | blocker | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['control_id']}` | `{row['status']}` | `{row['ready']}` | "
            f"`{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build enterprise/on-prem readiness gate.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--service-boundary-json", default=DEFAULT_SERVICE_BOUNDARY_JSON)
    parser.add_argument("--security-deployment-json", default=DEFAULT_SECURITY_DEPLOYMENT_JSON)
    parser.add_argument("--job-orchestration-json", default=DEFAULT_JOB_ORCHESTRATION_JSON)
    parser.add_argument("--rollout-readiness-json", default=DEFAULT_ROLLOUT_READINESS_JSON)
    parser.add_argument("--rollout-smoke-receipt-json", default=DEFAULT_ROLLOUT_SMOKE_RECEIPT_JSON)
    parser.add_argument("--license-audit-json", default=DEFAULT_LICENSE_AUDIT_JSON)
    parser.add_argument("--ledger-privacy-json", default=DEFAULT_LEDGER_PRIVACY_JSON)
    parser.add_argument("--api-customer-flow-json", default=DEFAULT_API_CUSTOMER_FLOW_JSON)
    parser.add_argument("--support-bundle-json", default=DEFAULT_SUPPORT_BUNDLE_JSON)
    parser.add_argument("--product-stage-roadmap-md", default=DEFAULT_PRODUCT_STAGE_ROADMAP_MD)
    parser.add_argument("--target-architecture-md", default=DEFAULT_TARGET_ARCHITECTURE_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_enterprise_on_prem_readiness_gate(
        root=root,
        service_boundary_json=args.service_boundary_json,
        security_deployment_json=args.security_deployment_json,
        job_orchestration_json=args.job_orchestration_json,
        rollout_readiness_json=args.rollout_readiness_json,
        rollout_smoke_receipt_json=args.rollout_smoke_receipt_json,
        license_audit_json=args.license_audit_json,
        ledger_privacy_json=args.ledger_privacy_json,
        api_customer_flow_json=args.api_customer_flow_json,
        support_bundle_json=args.support_bundle_json,
        product_stage_roadmap_md=args.product_stage_roadmap_md,
        target_architecture_md=args.target_architecture_md,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
