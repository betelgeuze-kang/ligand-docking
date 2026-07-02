from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_enterprise_on_prem_readiness_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_common_inputs(root: Path) -> None:
    _write_json(
        root / "runs/product_service_boundary_contract_current.json",
        {
            "summary": {
                "status": "product_service_boundary_contract_ready",
                "service_boundary_ready": True,
                "console_script_ready": True,
                "missing_api_route_count": 0,
                "missing_cli_command_count": 0,
                "api_route_count": 68,
                "cli_command_count": 25,
            }
        },
    )
    _write_json(
        root / "runs/product_security_deployment_contract_current.json",
        {
            "summary": {
                "status": "product_security_deployment_contract_ready",
                "auth_ready": True,
                "tenant_isolation_ready": True,
                "audit_log_ready": True,
                "metrics_endpoint_ready": True,
                "rollback_ready": True,
                "hosted_external_exposure_allowed": False,
                "tls_termination_operator_verified": False,
                "hosted_deployment_next_stage_required": "Approve hosted exposure after TLS.",
            }
        },
    )
    _write_json(
        root / "runs/product_job_orchestration_contract_current.json",
        {
            "summary": {
                "status": "product_job_orchestration_contract_ready",
                "product_job_orchestration_contract_ready": True,
                "worker_lease_heartbeat_ready": True,
                "retry_child_attempt_created": True,
                "idempotency_preserved": True,
                "retryable_failure_resume_ready": True,
            }
        },
    )
    _write_json(root / "runs/product_rollout_execution_readiness_current.json", {"summary": {}})
    _write_json(
        root / "runs/product_rollout_execution_smoke_receipt_current.json",
        {
            "summary": {
                "status": "product_rollout_execution_smoke_receipt_ready",
                "rollout_execution_smoke_receipt_ready": True,
                "rollout_executed": True,
                "ingress_certificate_verified_live": True,
                "target_environment": "k8s",
                "external_state_mutated": True,
            }
        },
    )
    _write_json(
        root / "runs/self_hosted_license_distribution_audit_current.json",
        {
            "summary": {
                "status": "self_hosted_license_distribution_audit_recorded",
                "hard_blocker_count": 0,
                "third_party_license_review_gate_ready": True,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
            }
        },
    )
    _write_json(
        root / "runs/product_ledger_privacy_scan_current.json",
        {"summary": {"status": "product_ledger_privacy_scan_ready", "ledger_privacy_scan_ready": True}},
    )
    _write_json(
        root / "runs/api_customer_flow_release_evidence_current.json",
        {
            "summary": {
                "status": "api_customer_flow_release_evidence_ready",
                "result_manifest_signature_verified": True,
            }
        },
    )
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "product_stage_and_roadmap_2026_06_30.md").write_text(
        "### Phase 6 - Enterprise Platform\nOIDC/RBAC, object storage, GPU scheduler.\n",
        encoding="utf-8",
    )
    (docs / "target_bioscience_architecture.md").write_text(
        "PostgreSQL durable queue GPU scheduler object storage OIDC/RBAC audit logs retry/restart.\n",
        encoding="utf-8",
    )


def _write_support_bundle(root: Path) -> None:
    _write_json(
        root / "runs/support_bundle_current.json",
        {
            "summary": {
                "status": "support_bundle_ready",
                "support_bundle_ready": True,
                "customer_safe_bundle_ready": True,
                "recovery_drill_ready": True,
                "incident_handoff_ready": True,
                "blocked_artifact_count": 0,
                "raw_customer_data_included": False,
                "secret_material_included": False,
            }
        },
    )


def test_enterprise_on_prem_gate_blocks_unproven_enterprise_controls(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)

    payload = mod.build_enterprise_on_prem_readiness_gate(root=tmp_path)

    summary = payload["summary"]
    rows = {row["control_id"]: row for row in payload["rows"]}
    assert summary["status"] == "blocked_enterprise_on_prem_readiness_gate"
    assert summary["enterprise_on_prem_ready"] is False
    assert summary["enterprise_platform_claim_allowed"] is False
    assert summary["control_count"] == 10
    assert summary["ready_control_count"] == 4
    assert summary["blocked_control_count"] == 6
    assert summary["primary_blocker_id"] == "oidc_rbac_tenant_isolation"
    assert summary["primary_blocker"] == "oidc_rbac_claim_grade_evidence_missing"
    assert summary["oidc_rbac_ready"] is False
    assert summary["object_storage_ready"] is False
    assert summary["gpu_scheduler_ready"] is False
    assert summary["audit_provenance_metrics_tracing_ready"] is False
    assert summary["license_control_ready"] is True
    assert summary["support_bundle_recovery_drill_ready"] is False
    assert summary["rollback_retry_idempotency_ready"] is True
    assert summary["source_external_state_mutated_count"] == 1
    assert rows["versioned_api_sdk_cli"]["ready"] is True
    assert rows["durable_queue_retry_idempotency"]["ready"] is True
    assert rows["license_control"]["ready"] is True
    assert rows["support_bundle_recovery_drill"]["blocker"] == "support_bundle_and_recovery_drill_missing"
    assert "oidc_ready=false" in rows["oidc_rbac_tenant_isolation"]["evidence"]
    assert "target_architecture_mentions_object_storage=true" in rows["object_storage_artifact_plane"]["evidence"]


def test_enterprise_on_prem_gate_consumes_ready_support_bundle(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    _write_support_bundle(tmp_path)

    payload = mod.build_enterprise_on_prem_readiness_gate(root=tmp_path)

    summary = payload["summary"]
    rows = {row["control_id"]: row for row in payload["rows"]}
    assert summary["status"] == "blocked_enterprise_on_prem_readiness_gate"
    assert summary["ready_control_count"] == 5
    assert summary["blocked_control_count"] == 5
    assert summary["support_bundle_recovery_drill_ready"] is True
    assert rows["support_bundle_recovery_drill"]["ready"] is True
    assert rows["support_bundle_recovery_drill"]["blocker"] == ""
    assert "support_bundle_ready=true" in rows["support_bundle_recovery_drill"]["evidence"]


def test_enterprise_on_prem_gate_cli_writes_outputs(tmp_path: Path) -> None:
    _write_common_inputs(tmp_path)
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"

    mod.main([
        "--root",
        str(tmp_path),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(out_csv),
        "--out-md",
        str(out_md),
    ])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == (
        "enterprise_on_prem_readiness_gate"
    )
    assert out_csv.read_text(encoding="utf-8").startswith("control_id,title,status,")
    assert "Enterprise On-Prem Readiness Gate" in out_md.read_text(encoding="utf-8")
