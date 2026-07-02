from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_support_bundle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_ready_inputs(root: Path) -> None:
    _write_json(
        root / "runs/product_security_deployment_contract_current.json",
        {
            "summary": {
                "status": "product_security_deployment_contract_ready",
                "audit_log_ready": True,
                "audit_retention_ready": True,
                "metrics_endpoint_ready": True,
                "rollback_ready": True,
                "blocker_count": 0,
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
                "idempotency_preserved": True,
                "retry_child_attempt_created": True,
                "retryable_failure_resume_ready": True,
                "blocked_check_count": 0,
            }
        },
    )
    _write_json(
        root / "runs/product_rollout_execution_smoke_receipt_current.json",
        {
            "summary": {
                "status": "product_rollout_execution_smoke_receipt_ready",
                "rollout_execution_smoke_receipt_ready": True,
                "rollout_executed": True,
                "ingress_certificate_verified_live": True,
                "target_environment": "k8s",
                "blocker_count": 0,
                "external_state_mutated": True,
            }
        },
    )
    _write_json(
        root / "runs/product_ledger_privacy_scan_current.json",
        {
            "summary": {
                "status": "product_ledger_privacy_scan_ready",
                "ledger_privacy_scan_ready": True,
                "blocker_count": 0,
                "leak_count": 0,
                "invalid_json_count": 0,
            }
        },
    )
    _write_json(
        root / "runs/api_customer_flow_release_evidence_current.json",
        {
            "summary": {
                "status": "api_customer_flow_release_evidence_ready",
                "result_manifest_signature_verified": True,
                "bundle_validation_ready": True,
                "restricted_unattended_runtime_ready": True,
                "tier_alpha_smoke_status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "blocker_count": 0,
            }
        },
    )
    _write_json(
        root / "runs/self_hosted_license_distribution_audit_current.json",
        {
            "summary": {
                "status": "self_hosted_license_distribution_audit_recorded",
                "third_party_license_review_gate_ready": True,
                "hard_blocker_count": 0,
                "spdx_license_id": "ProprietaryRef-Betelgeuze",
            }
        },
    )


def test_support_bundle_is_redacted_and_ready_when_required_artifacts_pass(tmp_path: Path) -> None:
    _write_ready_inputs(tmp_path)

    payload = mod.build_support_bundle(root=tmp_path)

    summary = payload["summary"]
    rows = {row["artifact_id"]: row for row in payload["rows"]}
    assert summary["status"] == "support_bundle_ready"
    assert summary["support_bundle_ready"] is True
    assert summary["customer_safe_bundle_ready"] is True
    assert summary["recovery_drill_ready"] is True
    assert summary["incident_handoff_ready"] is True
    assert summary["artifact_count"] == 6
    assert summary["ready_artifact_count"] == 6
    assert summary["blocked_artifact_count"] == 0
    assert summary["redacted_artifact_count"] == 6
    assert summary["raw_customer_data_included"] is False
    assert summary["secret_material_included"] is False
    assert summary["external_state_mutated"] is False
    assert rows["product_rollout_execution_smoke_receipt"]["safe_summary"]["external_state_mutated"] is True
    assert rows["product_rollout_execution_smoke_receipt"]["redacted_summary_only"] is True
    assert rows["product_rollout_execution_smoke_receipt"]["customer_raw_data_included"] is False
    assert rows["api_customer_flow_release_evidence"]["safe_summary"]["tier_alpha_smoke_status"] == (
        "tier_alpha_adrb2_dispatch_smoke_pass"
    )


def test_support_bundle_fails_closed_when_privacy_scan_has_leak(tmp_path: Path) -> None:
    _write_ready_inputs(tmp_path)
    _write_json(
        tmp_path / "runs/product_ledger_privacy_scan_current.json",
        {
            "summary": {
                "status": "product_ledger_privacy_scan_ready",
                "ledger_privacy_scan_ready": True,
                "blocker_count": 1,
                "leak_count": 1,
                "invalid_json_count": 0,
            }
        },
    )

    payload = mod.build_support_bundle(root=tmp_path)

    summary = payload["summary"]
    row = {
        item["artifact_id"]: item
        for item in payload["rows"]
    }["product_ledger_privacy_scan"]
    assert summary["status"] == "blocked_support_bundle"
    assert summary["support_bundle_ready"] is False
    assert summary["customer_safe_bundle_ready"] is False
    assert summary["primary_blocker_id"] == "product_ledger_privacy_scan"
    assert "nonzero:blocker_count" in row["blockers"]
    assert "nonzero:leak_count" in row["blockers"]


def test_support_bundle_cli_writes_outputs(tmp_path: Path) -> None:
    _write_ready_inputs(tmp_path)
    out_json = tmp_path / "support.json"
    out_csv = tmp_path / "support.csv"
    out_md = tmp_path / "support.md"

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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == "support_bundle"
    assert out_csv.read_text(encoding="utf-8").startswith("artifact_id,artifact_path,")
    assert "Support Bundle" in out_md.read_text(encoding="utf-8")
