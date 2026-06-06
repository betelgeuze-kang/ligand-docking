from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_security_deployment_contract as mod


def _write_minimal_repo(root: Path) -> None:
    (root / "api").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "docs").mkdir()
    (root / "api" / "config.py").write_text(
        (
            'PRODUCT_API_AUTH_REQUIRED PRODUCT_API_TOKEN PRODUCT_API_RATE_LIMIT_PER_MINUTE '
            'PRODUCT_API_MAX_PAYLOAD_BYTES PRODUCT_API_AUDIT_LOG_PATH '
            'PRODUCT_API_HOSTED_EXPOSURE_APPROVED os.getenv("PRODUCT_API_HOSTED_EXPOSURE_APPROVED", "0") == "1" '
            'PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED os.getenv("PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED", "0") == "1"'
        ),
        encoding="utf-8",
    )
    (root / "api" / "security.py").write_text(
        (
            "Authorization X-Tenant-ID _rate_limited payload_too_large ALLOWED_PRODUCT_PREFIXES path_not_allowed "
            "_audit_request self._audit_request(request, blocked.status_code) SECURITY_HEADERS X-Content-Type-Options "
            "X-Frame-Options Referrer-Policy _attach_security_headers(blocked) _attach_security_headers(response) "
            'def _blocked "status": "blocked" "execution_enabled": False "docking_results_emitted": False '
            '"external_state_mutated": False "authorization_present" "request_body_logged": False '
            '"authorization_value_logged": False def security_metrics_text generate_latest control="auth_hook" '
            'hosted_tls_termination_not_verified'
        ),
        encoding="utf-8",
    )
    (root / "api" / "main.py").write_text(
        'app.add_middleware(ProductSecurityMiddleware)\n@app.get("/metrics")\ndef metrics():\n    return security_metrics_text()\n',
        encoding="utf-8",
    )
    (root / "Dockerfile.product").write_text("FROM python:3.11-slim\nENV PRODUCT_API_AUTH_REQUIRED=1\n", encoding="utf-8")
    (root / "deploy" / "product_rollback_runbook.md").write_text("previous image digest\n/metrics\n", encoding="utf-8")
    (root / "docs" / "product_security_deployment_policy.md").write_text(
        (
            "API token hook\nPayload size limit\nRollback\n"
            "APPROVE_HOSTED_PRODUCT_API_EXPOSURE\n"
            "PRODUCT_API_HOSTED_EXPOSURE_APPROVED\n"
            "PRODUCT_API_TLS_TERMINATION_OPERATOR_VERIFIED=1\n"
        ),
        encoding="utf-8",
    )
    for requirement in ["requirements.txt", "requirements-api.txt", "requirements-deploy.txt"]:
        (root / requirement).write_text("pydantic==2.0.0\n", encoding="utf-8")


def test_product_security_deployment_contract_ready(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    payload = mod.build_product_security_deployment_contract(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "product_security_deployment_contract_ready"
    assert summary["security_deployment_ready"] is True
    assert summary["pass_count"] == summary["check_count"]
    assert summary["auth_ready"] is True
    assert summary["metrics_endpoint_ready"] is True
    assert summary["metrics_secret_free_ready"] is True
    assert summary["blocked_request_audit_ready"] is True
    assert summary["security_headers_ready"] is True
    assert summary["fail_closed_block_response_ready"] is True
    assert summary["audit_redaction_ready"] is True
    assert summary["sbom_ready"] is True
    assert summary["hosted_external_exposure_guard_ready"] is True
    assert summary["hosted_external_exposure_allowed"] is False
    assert summary["hosted_exposure_approval_token_required"] == "APPROVE_HOSTED_PRODUCT_API_EXPOSURE"
    assert summary["hosted_secret_injection_ready"] is False
    assert summary["tls_termination_operator_verified"] is False
    assert summary["hosted_deployment_contract_ready"] is True
    assert summary["hosted_deployment_currently_satisfied"] is False
    assert summary["hosted_deployment_blocked_stage_count"] == 5
    assert summary["hosted_deployment_blocked_stage_ids"][0] == "operator_exposure_approval"
    assert summary["hosted_deployment_next_stage_id"] == "operator_exposure_approval"


def test_product_security_deployment_contract_blocks_missing_container(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Dockerfile.product").unlink()

    payload = mod.build_product_security_deployment_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_security_deployment_contract"
    assert payload["summary"]["container_image_ready"] is False
    assert any(row["check"] == "container_image_ready" for row in payload["blockers"])


def test_product_security_deployment_contract_cli_writes_outputs(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path / "repo")
    out_json = tmp_path / "security.json"
    out_csv = tmp_path / "security.csv"
    out_md = tmp_path / "security.md"

    mod.main(
        [
            "--root",
            str(tmp_path / "repo"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["check_count"] == 17
    assert out_csv.exists()
    assert "# Product Security Deployment Contract" in out_md.read_text(encoding="utf-8")
