from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_product_rollout_execution_smoke_receipt as mod


def _readiness(**overrides: object) -> dict:
    summary = {
        "status": "product_rollout_execution_readiness_ready",
        "authorized_for_separate_operator_execution": True,
        "blocker_count": 0,
        "rollout_executed": False,
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _receipt_row(**overrides: str) -> dict[str, str]:
    row = {
        "operator_decision": "executed",
        "rollout_approval_token": "APPROVE_PRODUCT_ROLLOUT",
        "hosted_exposure_approval_token": "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        "target_environment": "k8s",
        "image_digest_or_tag": "registry.example/micf-api@sha256:abc",
        "rollout_command_summary": "kubectl set image deployment/micf-api ... && rollout status",
        "image_pushed": "true",
        "service_restarted": "true",
        "live_healthcheck_passed": "true",
        "metrics_scrape_verified": "true",
        "audit_log_write_verified": "true",
        "rollback_probe_verified": "true",
        "pager_provider_contacted": "true",
        "ingress_certificate_verified_live": "true",
        "external_state_mutated": "true",
        "operator_name": "Operator",
        "reviewed_at_utc": "2026-06-13T00:00:00Z",
        "operator_note": "R4 rollout smoke passed",
    }
    row.update(overrides)
    return row


def test_rollout_execution_smoke_receipt_blocks_missing_operator_receipt() -> None:
    payload = mod.build_product_rollout_execution_smoke_receipt(
        readiness_packet=_readiness(),
        receipt_rows=[],
        receipt_csv_present=False,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_product_rollout_execution_smoke_receipt"
    assert summary["rollout_execution_smoke_receipt_ready"] is False
    assert "operator_rollout_execution_smoke_receipt_csv_missing" in summary["blockers"]
    assert "operator_rollout_execution_smoke_receipt_row_missing" in summary["blockers"]
    assert summary["rollout_executed"] is False


def test_rollout_execution_smoke_receipt_ready_after_operator_execution_receipt() -> None:
    payload = mod.build_product_rollout_execution_smoke_receipt(
        readiness_packet=_readiness(),
        receipt_rows=[_receipt_row()],
        receipt_csv_present=True,
    )
    summary = payload["summary"]

    assert summary["status"] == "product_rollout_execution_smoke_receipt_ready"
    assert summary["rollout_execution_smoke_receipt_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["rollout_executed"] is True
    assert summary["external_state_mutated"] is True
    assert summary["pager_provider_contacted"] is True
    assert summary["ingress_certificate_verified_live"] is True
    assert payload["rows"][0]["receipt_status"] == "pass"


def test_rollout_execution_smoke_receipt_blocks_bad_receipt_row() -> None:
    payload = mod.build_product_rollout_execution_smoke_receipt(
        readiness_packet=_readiness(),
        receipt_rows=[
            _receipt_row(
                rollout_approval_token="WRONG",
                service_restarted="false",
                external_state_mutated="false",
                reviewed_at_utc="not-a-date",
            )
        ],
        receipt_csv_present=True,
    )
    blockers = set(payload["summary"]["blockers"])

    assert payload["summary"]["status"] == "blocked_product_rollout_execution_smoke_receipt"
    assert "rollout_approval_token_mismatch" in blockers
    assert "service_restarted_not_true" in blockers
    assert "external_state_mutated_not_true" in blockers
    assert "reviewed_at_utc_invalid" in blockers


def test_rollout_execution_smoke_receipt_cli_writes_outputs_and_template(tmp_path: Path) -> None:
    readiness_json = tmp_path / "readiness.json"
    receipt_csv = tmp_path / "receipt.csv"
    template_csv = tmp_path / "template.csv"
    out_json = tmp_path / "receipt.json"
    out_csv = tmp_path / "receipt_out.csv"
    out_md = tmp_path / "receipt.md"
    readiness_json.write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")
    with receipt_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_receipt_row().keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerow(_receipt_row())

    mod.main(
        [
            "--readiness-json",
            str(readiness_json),
            "--receipt-csv",
            str(receipt_csv),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == (
        "product_rollout_execution_smoke_receipt_ready"
    )
    assert template_csv.read_text(encoding="utf-8").startswith("operator_decision,")
    assert out_csv.read_text(encoding="utf-8").startswith("receipt_status,")
    assert "Product Rollout Execution Smoke Receipt" in out_md.read_text(encoding="utf-8")
