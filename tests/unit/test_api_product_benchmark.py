from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_public_benchmark_external_receipts_endpoint_missing_attach_packet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.product_benchmark as mod

    monkeypatch.setattr(
        mod,
        "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT",
        tmp_path / "missing_audit.json",
    )
    monkeypatch.setattr(
        mod,
        "PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT",
        tmp_path / "missing_attach.json",
    )

    response = TestClient(app).get("/product/public-benchmark-external-receipts-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_public_benchmark_external_receipts_audit"
    assert body["external_benchmark_receipts_ready"] is False
    assert body["receipt_attach_packet_present"] is False
    assert body["receipt_attach_packet_ready"] is False
    assert body["field_work_order_ready"] is False
    assert body["field_work_order_row_count"] == 0
    assert body["field_work_order_pending_field_count"] == 0
    assert body["field_work_order_rows"] == []
    assert body["claim_promotion_allowed"] is False
    assert body["execution_enabled"] is False
    assert body["external_state_mutated"] is False


def test_public_benchmark_external_receipts_endpoint_surfaces_attach_work_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.product_benchmark as mod

    audit = tmp_path / "runs/public_benchmark_external_receipts_audit_current.json"
    attach = tmp_path / "runs/public_benchmark_receipt_attach_packet_current.json"
    monkeypatch.setattr(mod, "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT", audit)
    monkeypatch.setattr(mod, "PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_ARTIFACT", attach)
    _write_json(
        audit,
        {
            "summary": {
                "status": "blocked_public_benchmark_external_receipts_audit",
                "external_benchmark_receipts_ready": False,
                "claim_promotion_allowed": False,
                "step_count": 7,
                "ready_step_count": 5,
                "blocked_step_count": 2,
                "blocker_count": 2,
                "blockers": [
                    "vina_gnina_same_input_comparison:vina_gnina_same_input_score_evidence_missing",
                    "benchmark_receipt_attach:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "primary_blocker_id": "vina_gnina_same_input_comparison",
                "primary_blocker": "vina_gnina_same_input_score_evidence_missing",
                "primary_blocker_next_required_step": "Fill Vina/GNINA same-input scores.",
                "next_required_step": "Fill Vina/GNINA same-input scores.",
                "vina_gnina_score_value_pending_count": 32,
                "vina_gnina_pending_field_count": 192,
                "receipt_blocked_row_count": 51,
                "benchmark_ledger_entry_count": 4,
                "benchmark_ledger_external_safe_count": 2,
            },
            "rows": [
                {
                    "step_id": "vina_gnina_same_input_comparison",
                    "status": "blocked",
                    "ready": False,
                    "blocker": "vina_gnina_same_input_score_evidence_missing",
                    "next_required_step": "Fill Vina/GNINA same-input scores.",
                }
            ],
        },
    )
    _write_json(
        attach,
        {
            "summary": {
                "status": "blocked_public_benchmark_receipt_attach_packet",
                "receipt_attach_packet_ready": False,
                "blocker_count": 2,
                "blockers": [
                    "vina_gnina_same_input_scores:vina_gnina_same_input_score_evidence_missing",
                    "metric_source_receipt_rows:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "primary_blocker_id": "vina_gnina_same_input_scores",
                "primary_blocker": "vina_gnina_same_input_score_evidence_missing",
                "next_required_step": "Fill every Vina/GNINA same-input score template row.",
                "field_work_order_ready": False,
                "field_work_order_row_count": 2,
                "field_work_order_pending_field_count": 19,
                "field_work_order_primary_lane_id": "vina_gnina_same_input_scores",
                "field_work_order_primary_field_name": "approval_token",
                "field_work_order_primary_pending_row_count": 16,
                "field_work_order_primary_required_value": (
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                ),
                "field_work_order_primary_required_action": (
                    "Fill approval_token with "
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES after operator review."
                ),
                "field_work_order_primary_approval_token_required": (
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                ),
                "field_work_order_primary_operator_csv": (
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "field_work_order_primary_source_artifact": (
                    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                ),
                "metric_source_receipt_csv": (
                    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
                ),
                "metric_source_receipt_row_count": 51,
                "metric_source_receipt_blocked_row_count": 51,
                "metric_source_receipt_manual_field_pending_count": 510,
                "metric_source_receipt_approval_token_pending_count": 51,
            },
            "field_work_order_rows": [
                {
                    "lane_id": "vina_gnina_same_input_scores",
                    "field_name": "approval_token",
                    "pending_row_count": 16,
                    "source_artifact": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
                    "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
                    "required_value": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                    ),
                    "approval_token_required": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                    ),
                    "required_action": (
                        "Fill approval_token with "
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES after operator review."
                    ),
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )

    response = TestClient(app).get("/product/public-benchmark-external-receipts-audit")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked_public_benchmark_external_receipts_audit"
    assert body["ready_step_count"] == 5
    assert body["blocked_step_count"] == 2
    assert body["receipt_attach_packet_present"] is True
    assert body["receipt_attach_packet_ready"] is False
    assert body["receipt_attach_blocker_count"] == 2
    assert body["receipt_attach_primary_blocker_id"] == "vina_gnina_same_input_scores"
    assert body["field_work_order_row_count"] == 2
    assert body["field_work_order_pending_field_count"] == 19
    assert body["field_work_order_primary_field_name"] == "approval_token"
    assert body["field_work_order_primary_pending_row_count"] == 16
    assert body["field_work_order_rows"][0]["lane_id"] == "vina_gnina_same_input_scores"
    assert body["field_work_order_rows"][0]["execution_enabled"] is False
    assert body["field_work_order_rows"][0]["external_state_mutated"] is False
    assert body["field_work_order_rows"][0]["claim_promotion_allowed"] is False
    assert body["metric_source_receipt_approval_token_pending_count"] == 51
    assert body["claim_promotion_allowed"] is False
