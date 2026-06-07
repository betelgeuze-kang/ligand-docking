from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_rollout_execution_readiness as mod


def _release() -> dict:
    return {"status": "release_bundle_ready_for_operator_review", "blocker_count": 0}


def _rollout() -> dict:
    return {"status": "planned", "dry_run": True, "approval_token_required": "APPROVE_PRODUCT_ROLLOUT"}


def _security() -> dict:
    return {"summary": {"status": "product_security_deployment_contract_ready", "security_deployment_ready": True}}


def _alert() -> dict:
    return {"status": "pass", "received_alert_count": 1}


def _operator_row(**overrides: str) -> dict[str, str]:
    row = {
        "operator_decision": "approve",
        "rollout_approval_token": "APPROVE_PRODUCT_ROLLOUT",
        "hosted_exposure_approval_token": "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        "target_environment": "k8s",
        "image_digest_or_tag": "registry.example/micf-api@sha256:abc",
        "registry_context_verified": "true",
        "k8s_or_compose_context_verified": "true",
        "tls_termination_verified": "true",
        "pager_webhook_secret_mounted": "true",
        "rollback_reference_verified": "true",
        "operator_name": "Operator",
        "reviewed_at_utc": "2026-06-06T00:00:00Z",
        "operator_note": "ready",
    }
    row.update(overrides)
    return row


def test_product_rollout_execution_readiness_blocks_missing_operator_intake() -> None:
    payload = mod.build_product_rollout_execution_readiness(
        release_bundle_packet=_release(),
        rollout_plan_packet=_rollout(),
        security_contract_packet=_security(),
        alert_smoke_packet=_alert(),
        operator_rows=[],
        operator_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_rollout_execution_readiness"
    assert summary["release_bundle_ready"] is True
    assert summary["rollout_plan_ready"] is True
    assert summary["security_contract_ready"] is True
    assert summary["alert_smoke_ready"] is True
    assert "operator_rollout_execution_csv_missing" in summary["blockers"]
    assert "operator_decision_missing" in summary["blockers"]
    assert summary["rollout_executed"] is False
    assert summary["pager_provider_contacted"] is False
    assert summary["external_state_mutated"] is False


def test_product_rollout_execution_readiness_ready_for_separate_execution_only() -> None:
    payload = mod.build_product_rollout_execution_readiness(
        release_bundle_packet=_release(),
        rollout_plan_packet=_rollout(),
        security_contract_packet=_security(),
        alert_smoke_packet=_alert(),
        operator_rows=[_operator_row()],
        operator_csv_present=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_rollout_execution_readiness_ready"
    assert summary["authorized_for_separate_operator_execution"] is True
    assert summary["blocker_count"] == 0
    assert summary["rollout_executed"] is False
    assert summary["image_pushed"] is False
    assert summary["service_restarted"] is False
    assert payload["rows"][0]["rollout_execution_readiness_status"] == "approved_for_separate_operator_execution"


def test_product_rollout_execution_readiness_blocks_bad_operator_row() -> None:
    payload = mod.build_product_rollout_execution_readiness(
        release_bundle_packet=_release(),
        rollout_plan_packet=_rollout(),
        security_contract_packet=_security(),
        alert_smoke_packet=_alert(),
        operator_rows=[
            _operator_row(
                rollout_approval_token="WRONG",
                hosted_exposure_approval_token="WRONG",
                target_environment="prod",
                image_digest_or_tag="",
                registry_context_verified="false",
                operator_name="",
            )
        ],
        operator_csv_present=True,
    )
    blockers = set(payload["summary"]["blockers"])

    assert payload["summary"]["status"] == "blocked_product_rollout_execution_readiness"
    assert "rollout_approval_token_mismatch" in blockers
    assert "hosted_exposure_approval_token_mismatch" in blockers
    assert "target_environment_invalid" in blockers
    assert "image_digest_or_tag_missing" in blockers
    assert "registry_context_verified_not_confirmed" in blockers
    assert "operator_name_missing" in blockers


def test_product_rollout_execution_readiness_tool_writes_outputs_and_template(tmp_path: Path) -> None:
    release_json = tmp_path / "release.json"
    rollout_json = tmp_path / "rollout.json"
    security_json = tmp_path / "security.json"
    alert_json = tmp_path / "alert.json"
    intake_csv = tmp_path / "intake.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "readiness.json"
    out_csv = tmp_path / "readiness.csv"
    out_md = tmp_path / "readiness.md"
    release_json.write_text(json.dumps(_release()) + "\n", encoding="utf-8")
    rollout_json.write_text(json.dumps(_rollout()) + "\n", encoding="utf-8")
    security_json.write_text(json.dumps(_security()) + "\n", encoding="utf-8")
    alert_json.write_text(json.dumps(_alert()) + "\n", encoding="utf-8")
    with intake_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_operator_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_operator_row())

    mod.main(
        [
            "--release-bundle-json",
            str(release_json),
            "--rollout-plan-json",
            str(rollout_json),
            "--security-contract-json",
            str(security_json),
            "--alert-smoke-json",
            str(alert_json),
            "--operator-intake-csv",
            str(intake_csv),
            "--template-csv",
            str(template_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_rollout_execution_readiness_ready"
    assert template_csv.read_text(encoding="utf-8").startswith("operator_decision,rollout_approval_token,")
    assert out_csv.read_text(encoding="utf-8").startswith("rollout_execution_readiness_status,")
    assert "Product Rollout Execution Readiness" in out_md.read_text(encoding="utf-8")
