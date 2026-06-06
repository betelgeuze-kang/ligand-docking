#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_security_deployment_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_security_deployment_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_security_deployment_contract_current.md"
CLAIM_BOUNDARY = (
    "Product security/deployment contract only; statically audits local hosted/customer API controls, deployment "
    "artifacts, SBOM manifest evidence, metrics route, and rollback documentation. It does not start a server, build "
    "containers, inject secrets, expose an API, upload, deploy, email, delete, or mutate external state."
)


def _resolve(root: str | Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path(root).resolve() / path


def _read_text(root: str | Path, path_like: str | Path) -> str:
    path = _resolve(root, path_like)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(check: str, passed: bool, observed: str, required: str, artifact: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact": artifact,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


def build_product_security_deployment_contract(*, root: str | Path = ROOT) -> dict[str, Any]:
    root_path = Path(root).resolve()
    security_py = _read_text(root_path, "api/security.py")
    main_py = _read_text(root_path, "api/main.py")
    config_py = _read_text(root_path, "api/config.py")
    dockerfile = _read_text(root_path, "Dockerfile.product")
    rollback = _read_text(root_path, "deploy/product_rollback_runbook.md")
    policy = _read_text(root_path, "docs/product_security_deployment_policy.md")
    requirements = [
        "requirements.txt",
        "requirements-api.txt",
        "requirements-deploy.txt",
    ]
    sbom_rows = []
    for requirement in requirements:
        path = _resolve(root_path, requirement)
        sbom_rows.append({"path": requirement, "sha256": _sha256(path), "present": path.is_file()})
    sbom_ready = all(row["present"] and row["sha256"] for row in sbom_rows)

    auth_ready = "PRODUCT_API_AUTH_REQUIRED" in config_py and "PRODUCT_API_TOKEN" in config_py and "Authorization" in security_py
    tenant_ready = "X-Tenant-ID" in security_py
    rate_limit_ready = "PRODUCT_API_RATE_LIMIT_PER_MINUTE" in config_py and "_rate_limited" in security_py
    payload_limit_ready = "PRODUCT_API_MAX_PAYLOAD_BYTES" in config_py and "payload_too_large" in security_py
    path_allowlist_ready = "ALLOWED_PRODUCT_PREFIXES" in security_py and "path_not_allowed" in security_py
    audit_log_ready = "PRODUCT_API_AUDIT_LOG_PATH" in config_py and "_audit_request" in security_py
    blocked_audit_ready = "self._audit_request(request, blocked.status_code)" in security_py
    security_headers_ready = (
        "SECURITY_HEADERS" in security_py
        and "X-Content-Type-Options" in security_py
        and "X-Frame-Options" in security_py
        and "Referrer-Policy" in security_py
        and "_attach_security_headers(blocked)" in security_py
        and "_attach_security_headers(response)" in security_py
    )
    fail_closed_block_response_ready = (
        "def _blocked" in security_py
        and '"status": "blocked"' in security_py
        and '"execution_enabled": False' in security_py
        and '"docking_results_emitted": False' in security_py
        and '"external_state_mutated": False' in security_py
    )
    blocked_shape_present = "def _blocked" in security_py
    blocked_execution_false = '"execution_enabled": False' in security_py
    blocked_docking_false = '"docking_results_emitted": False' in security_py
    blocked_external_false = '"external_state_mutated": False' in security_py
    audit_redaction_ready = (
        '"authorization_present"' in security_py
        and '"request_body_logged": False' in security_py
        and '"authorization_value_logged": False' in security_py
        and "product_api_token" not in security_py.partition("def _audit_request")[2]
    )
    audit_authorization_present_flag = '"authorization_present"' in security_py
    audit_request_body_logged_false = '"request_body_logged": False' in security_py
    audit_authorization_value_logged_false = '"authorization_value_logged": False' in security_py
    hosted_exposure_guard_ready = (
        "PRODUCT_API_HOSTED_EXPOSURE_APPROVED" in config_py
        and '"0") == "1"' in config_py
        and "APPROVE_HOSTED_PRODUCT_API_EXPOSURE" in policy
        and "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED" in config_py
        and "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1" in policy
        and "hosted_tls_termination_not_verified" in security_py
    )
    hosted_external_exposure_allowed = False
    hosted_exposure_approval_token_required = "APPROVE_HOSTED_PRODUCT_API_EXPOSURE"
    hosted_secret_injection_ready = False
    tls_termination_operator_verified = False
    hosted_secret_injection_operator_verified = False
    hosted_tls_termination_operator_verified = False
    metrics_route_present = '@app.get("/metrics"' in main_py
    metrics_func_present = "security_metrics_text" in main_py
    metrics_secret_free_ready = (
        "PRODUCT_API_TOKEN" not in security_py.partition("def security_metrics_text")[2]
        and "product_api_token" not in security_py.partition("def security_metrics_text")[2]
        and "auth_hook" in security_py
        and "generate_latest" in security_py.partition("def security_metrics_text")[2]
    )
    metrics_ready = metrics_route_present and metrics_func_present
    middleware_ready = "app.add_middleware(ProductSecurityMiddleware)" in main_py
    container_ready = "FROM python:3.11-slim" in dockerfile and "PRODUCT_API_AUTH_REQUIRED=1" in dockerfile
    rollback_ready = "previous image digest" in rollback and "/metrics" in rollback
    policy_ready = "API token hook" in policy and "Payload size limit" in policy and "Rollback" in policy

    rows = [
        _row("auth_ready", auth_ready, f"auth_required={'PRODUCT_API_AUTH_REQUIRED' in config_py};authorization={'Authorization' in security_py}", "env-driven API token hook", "api/config.py;api/security.py", "Hosted API exposure needs an authentication hook."),
        _row("tenant_isolation_ready", tenant_ready, f"x_tenant={'X-Tenant-ID' in security_py}", "tenant marker captured for audit/rate separation", "api/security.py", "Customer traffic needs tenant-aware request accounting."),
        _row("rate_limit_ready", rate_limit_ready, f"rate_config={'PRODUCT_API_RATE_LIMIT_PER_MINUTE' in config_py};rate_func={'_rate_limited' in security_py}", "per tenant/client rate limiter", "api/config.py;api/security.py", "Hosted API exposure needs denial-of-service guardrails."),
        _row("payload_limit_ready", payload_limit_ready, f"payload_config={'PRODUCT_API_MAX_PAYLOAD_BYTES' in config_py};blocker={'payload_too_large' in security_py}", "request payload size limit", "api/config.py;api/security.py", "Raw molecular payloads need a hard size boundary."),
        _row("path_allowlist_ready", path_allowlist_ready, f"allowlist={'ALLOWED_PRODUCT_PREFIXES' in security_py};blocker={'path_not_allowed' in security_py}", "path allowlist blocker", "api/security.py", "Hosted API exposure needs a narrow route surface."),
        _row("audit_log_ready", audit_log_ready, f"audit_config={'PRODUCT_API_AUDIT_LOG_PATH' in config_py};audit_func={'_audit_request' in security_py}", "JSONL audit log hook", "api/config.py;api/security.py", "Customer operations need traceable request logs."),
        _row(
            "blocked_request_audit_ready",
            blocked_audit_ready,
            f"blocked_audit={blocked_audit_ready}",
            "preflight-blocked requests are audit logged with status code",
            "api/security.py",
            "Security audit trails must include rejected requests, not only successful handler calls.",
        ),
        _row(
            "security_headers_ready",
            security_headers_ready,
            (
                f"headers={'SECURITY_HEADERS' in security_py};"
                f"blocked_headers={'_attach_security_headers(blocked)' in security_py};"
                f"response_headers={'_attach_security_headers(response)' in security_py}"
            ),
            "security headers attached to both allowed and blocked responses",
            "api/security.py",
            "Hosted API responses should consistently set browser/client hardening headers.",
        ),
        _row(
            "fail_closed_block_response_ready",
            fail_closed_block_response_ready,
            (
                f"blocked_shape={blocked_shape_present};"
                f"execution_false={blocked_execution_false};"
                f"docking_false={blocked_docking_false};"
                f"external_false={blocked_external_false}"
            ),
            "blocked responses include fail-closed execution, docking-result, and external-state flags",
            "api/security.py",
            "Customers should see an explicit fail-closed response when a hosted control blocks a request.",
        ),
        _row(
            "audit_redaction_ready",
            audit_redaction_ready,
            (
                f"authorization_present_flag={audit_authorization_present_flag};"
                f"request_body_logged_false={audit_request_body_logged_false};"
                f"authorization_value_logged_false={audit_authorization_value_logged_false}"
            ),
            "audit log records presence/metadata only and does not log request bodies or authorization values",
            "api/security.py",
            "Hosted audit logs must preserve traceability without storing raw molecular payloads or bearer tokens.",
        ),
        _row(
            "hosted_external_exposure_guard_ready",
            hosted_exposure_guard_ready,
            (
                f"hosted_exposure_flag={'PRODUCT_API_HOSTED_EXPOSURE_APPROVED' in config_py};"
                f"tls_operator_flag={'PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED' in config_py};"
                f"runtime_tls_blocker={'hosted_tls_termination_not_verified' in security_py};"
                f"approval_token_documented={'APPROVE_HOSTED_PRODUCT_API_EXPOSURE' in policy};"
                f"hosted_external_exposure_allowed={hosted_external_exposure_allowed}"
            ),
            "hosted exposure remains disabled unless operator approval, secret injection, and TLS verification are explicitly present",
            "api/config.py;docs/product_security_deployment_policy.md",
            "Hosted/customer API claims must fail closed unless environment-specific exposure approval is explicit.",
        ),
        _row("middleware_registered", middleware_ready, f"registered={middleware_ready}", "ProductSecurityMiddleware registered on FastAPI app", "api/main.py", "Security controls must be attached to the app, not just defined."),
        _row("metrics_endpoint_ready", metrics_ready and metrics_secret_free_ready, f"metrics_route={metrics_route_present};metrics_func={metrics_func_present};metrics_secret_free={metrics_secret_free_ready}", "/metrics route available without secret/token disclosure", "api/main.py;api/security.py", "Deployment monitoring needs a scrapeable smoke endpoint that does not leak secrets."),
        _row("sbom_ready", sbom_ready, ";".join(f"{row['path']}={row['sha256'][:12] or 'missing'}" for row in sbom_rows), "requirements manifest sha256 inventory", ";".join(requirements), "Release review needs dependency manifest provenance."),
        _row("container_image_ready", container_ready, f"dockerfile_present={bool(dockerfile)};auth_env={'PRODUCT_API_AUTH_REQUIRED=1' in dockerfile}", "product Dockerfile with security env defaults", "Dockerfile.product", "Hosted/customer deployment needs a reproducible container recipe."),
        _row("rollback_ready", rollback_ready, f"rollback_doc={bool(rollback)};metrics={'/metrics' in rollback}", "rollback runbook with image digest and smoke checks", "deploy/product_rollback_runbook.md", "Commercial deployment needs a rollback plan."),
        _row("security_policy_ready", policy_ready, f"policy_doc={bool(policy)}", "security/deployment policy documents operator boundaries", "docs/product_security_deployment_policy.md", "Security controls need an operator-facing policy boundary."),
    ]
    failed = [row for row in rows if row["status"] != "pass"]
    ready = not failed
    hosted_deployment_contract_ready = bool(ready and hosted_exposure_guard_ready)
    hosted_deployment_currently_satisfied = bool(
        hosted_deployment_contract_ready
        and hosted_external_exposure_allowed
        and hosted_secret_injection_ready
        and tls_termination_operator_verified
        and hosted_secret_injection_operator_verified
        and hosted_tls_termination_operator_verified
    )
    hosted_deployment_blocked_stage_ids = [
        stage_id
        for stage_id, satisfied in [
            ("operator_exposure_approval", hosted_external_exposure_allowed),
            ("hosted_secret_injection", hosted_secret_injection_ready),
            ("tls_termination_verification", tls_termination_operator_verified),
            ("secret_injection_operator_verification", hosted_secret_injection_operator_verified),
            ("tls_operator_verification", hosted_tls_termination_operator_verified),
        ]
        if not satisfied
    ]
    summary = {
        "packet_type": "product_security_deployment_contract",
        "status": "product_security_deployment_contract_ready" if ready else "blocked_product_security_deployment_contract",
        "security_deployment_ready": ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(failed),
        "auth_ready": auth_ready,
        "tenant_isolation_ready": tenant_ready,
        "rate_limit_ready": rate_limit_ready,
        "payload_limit_ready": payload_limit_ready,
        "path_allowlist_ready": path_allowlist_ready,
        "audit_log_ready": audit_log_ready,
        "blocked_request_audit_ready": blocked_audit_ready,
        "security_headers_ready": security_headers_ready,
        "fail_closed_block_response_ready": fail_closed_block_response_ready,
        "audit_redaction_ready": audit_redaction_ready,
        "hosted_external_exposure_guard_ready": hosted_exposure_guard_ready,
        "hosted_external_exposure_allowed": hosted_external_exposure_allowed,
        "hosted_exposure_approval_token_required": hosted_exposure_approval_token_required,
        "hosted_secret_injection_ready": hosted_secret_injection_ready,
        "tls_termination_operator_verified": tls_termination_operator_verified,
        "hosted_secret_injection_operator_verified": hosted_secret_injection_operator_verified,
        "hosted_tls_termination_operator_verified": hosted_tls_termination_operator_verified,
        "hosted_deployment_contract_ready": hosted_deployment_contract_ready,
        "hosted_deployment_currently_satisfied": hosted_deployment_currently_satisfied,
        "hosted_deployment_blocked_stage_count": len(hosted_deployment_blocked_stage_ids),
        "hosted_deployment_blocked_stage_ids": hosted_deployment_blocked_stage_ids,
        "hosted_deployment_next_stage_id": hosted_deployment_blocked_stage_ids[0]
        if hosted_deployment_blocked_stage_ids
        else "",
        "hosted_deployment_next_stage_required": (
            "Set APPROVE_HOSTED_PRODUCT_API_EXPOSURE only after secret injection and TLS termination are operator verified."
            if hosted_deployment_blocked_stage_ids
            else "Hosted deployment controls are currently satisfied."
        ),
        "middleware_registered": middleware_ready,
        "sbom_ready": sbom_ready,
        "container_image_ready": container_ready,
        "metrics_endpoint_ready": metrics_ready and metrics_secret_free_ready,
        "metrics_secret_free_ready": metrics_secret_free_ready,
        "rollback_ready": rollback_ready,
        "security_policy_ready": policy_ready,
        "sbom_rows": sbom_rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Security/deployment contract is ready for hosted-candidate review; external exposure still requires environment-specific approval and secrets."
            if ready
            else "Repair failed security/deployment checks before hosted or external customer API claims."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": failed}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(ROOT, path_like)
    s = payload["summary"]
    lines = [
        "# Product Security Deployment Contract",
        "",
        f"- status: `{s['status']}`",
        f"- security_deployment_ready: `{s['security_deployment_ready']}`",
        f"- hosted_deployment_contract_ready: `{s['hosted_deployment_contract_ready']}`",
        f"- hosted_deployment_currently_satisfied: `{s['hosted_deployment_currently_satisfied']}`",
        f"- hosted_deployment_next_stage_id: `{s['hosted_deployment_next_stage_id']}`",
        f"- pass_count: `{s['pass_count']}` / `{s['check_count']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | reason |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | {row['reason']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product security/deployment contract.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_security_deployment_contract(root=args.root)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(ROOT, args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
