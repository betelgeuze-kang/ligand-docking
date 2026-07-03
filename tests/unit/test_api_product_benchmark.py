from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_public_benchmark_endpoint_exposes_scorecard_panel_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.product_benchmark as mod

    work_order = tmp_path / "runs/product_public_benchmark_work_order_current.json"
    receipts = tmp_path / "runs/public_benchmark_external_receipts_audit_current.json"
    monkeypatch.setattr(mod, "PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT", work_order)
    monkeypatch.setattr(mod, "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT", receipts)
    _write_json(
        work_order,
        {
            "summary": {
                "status": "product_public_benchmark_work_order_clear",
                "public_benchmark_validation_ready": True,
                "suite_count": 2,
                "open_suite_count": 2,
                "suite_result_provenance_present_count": 1,
                "local_artifact_preflight_ready_suite_count": 1,
            },
            "rows": [
                {
                    "suite_id": "lit_pcba_virtual_screening",
                    "benchmark_family": "protein_ligand_virtual_screening",
                    "required_for_commercial_release": True,
                    "work_order_status": "ready",
                    "scorecard_status": "lit_pcba_scorecard_pass",
                    "primary_metric": "EF1",
                    "primary_metric_value": "4.7",
                    "primary_metric_threshold": "1.2",
                    "scorecard_row_csv": "runs/lit_pcba_scorecard_row_current.csv",
                    "scorecard_row": "runs/lit_pcba_scorecard_current.json",
                    "materialization_status": "lit_pcba_materialization_ready",
                    "materialization_manifest": "runs/lit_pcba_materialization_manifest_current.json",
                    "result_provenance_json": "runs/lit_pcba_result_provenance_current.json",
                    "result_provenance_present": True,
                    "local_artifact_preflight_ready": True,
                    "scorecard_blockers": "",
                    "blocker": "",
                    "execution_enabled": True,
                    "docking_results_emitted": True,
                    "external_state_mutated": True,
                },
                {
                    "suite_id": "pdbbind_casf_pose_affinity",
                    "benchmark_family": "protein_ligand_pose_affinity",
                    "required_for_commercial_release": True,
                    "work_order_status": "blocked",
                    "scorecard_status": "blocked_public_benchmark_suite_scorecard",
                    "primary_metric": "pose_success_rate",
                    "primary_metric_value": "0.1",
                    "primary_metric_threshold": "0.35",
                    "scorecard_row_csv": "runs/pdbbind_scorecard_row_current.csv",
                    "scorecard_row": "runs/pdbbind_scorecard_current.json",
                    "materialization_status": "blocked_public_benchmark_materialization",
                    "result_provenance_json": "",
                    "result_provenance_present": False,
                    "local_artifact_preflight_ready": False,
                    "scorecard_blockers": "primary_metric_below_threshold;result_provenance_missing",
                    "blocker": "local_artifact_preflight_blocked",
                    "refresh_command": "python3 tools/build_product_public_benchmark_work_order.py",
                    "execution_enabled": True,
                    "docking_results_emitted": True,
                    "external_state_mutated": True,
                },
            ],
        },
    )
    _write_json(
        receipts,
        {
            "summary": {
                "status": "blocked_public_benchmark_external_receipts_audit",
                "external_benchmark_receipts_ready": False,
                "claim_promotion_allowed": False,
                "blocker_count": 2,
                "blockers": [
                    "vina_gnina_same_input_comparison:vina_gnina_same_input_score_evidence_missing",
                    "benchmark_receipt_attach:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "primary_blocker_next_required_step": "Fill Vina/GNINA same-input scores.",
            }
        },
    )

    response = TestClient(app).get("/product/public-benchmark")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "product_public_benchmark_work_order_clear"
    assert body["scorecard_panel_ready"] is False
    assert body["suite_row_count"] == 2
    assert body["suite_green_row_count"] == 1
    assert body["suite_blocked_row_count"] == 1
    assert body["scorecard_blocker_row_count"] == 1
    assert body["suite_rows"][0] == {
        "suite_id": "lit_pcba_virtual_screening",
        "benchmark_family": "protein_ligand_virtual_screening",
        "required_for_commercial_release": True,
        "work_order_status": "ready",
        "scorecard_status": "lit_pcba_scorecard_pass",
        "scorecard_ready": True,
        "primary_metric": "EF1",
        "primary_metric_value": 4.7,
        "primary_metric_threshold": 1.2,
        "primary_metric_gate_pass": True,
        "scorecard_row_csv": "runs/lit_pcba_scorecard_row_current.csv",
        "scorecard_artifact": "runs/lit_pcba_scorecard_current.json",
        "materialization_status": "lit_pcba_materialization_ready",
        "materialization_manifest": "runs/lit_pcba_materialization_manifest_current.json",
        "result_provenance_json": "runs/lit_pcba_result_provenance_current.json",
        "result_provenance_present": True,
        "local_artifact_preflight_ready": True,
        "missing_local_input_artifact_count": 0,
        "missing_local_output_artifact_count": 0,
        "blockers": [],
        "operator_action_required": False,
        "recommended_next_action": "review_public_benchmark_scorecard",
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }
    assert body["scorecard_blocker_rows"][0]["suite_id"] == "pdbbind_casf_pose_affinity"
    assert body["scorecard_blocker_rows"][0]["primary_metric_gate_pass"] is False
    assert body["scorecard_blocker_rows"][0]["claim_promotion_allowed"] is False
    assert body["external_receipts_status"] == "blocked_public_benchmark_external_receipts_audit"
    assert body["external_receipts_ready"] is False
    assert body["external_receipts_blocker_count"] == 2
    assert body["external_receipt_blocker_row_count"] == 2
    assert body["external_receipt_blocker_rows"][0]["blocker_id"] == (
        "vina_gnina_same_input_comparison"
    )
    assert body["external_beta_claim_allowed"] is False
    assert body["claim_promotion_allowed"] is False
    assert body["execution_enabled"] is False
    assert body["docking_results_emitted"] is False
    assert body["external_state_mutated"] is False


def test_public_benchmark_endpoint_is_fail_closed_when_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import api.product_benchmark as mod

    monkeypatch.setattr(
        mod,
        "PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT",
        tmp_path / "missing_work_order.json",
    )
    monkeypatch.setattr(
        mod,
        "PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT",
        tmp_path / "missing_receipts.json",
    )

    response = TestClient(app).get("/product/public-benchmark")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_product_public_benchmark_work_order"
    assert body["scorecard_panel_ready"] is False
    assert body["suite_row_count"] == 0
    assert body["suite_rows"] == []
    assert body["scorecard_blocker_row_count"] == 1
    assert body["scorecard_blocker_rows"][0]["blocker_id"] == (
        "product_public_benchmark_work_order_missing"
    )
    assert body["external_receipts_ready"] is False
    assert body["external_receipt_blocker_rows"] == []
    assert body["external_beta_claim_allowed"] is False
    assert body["execution_enabled"] is False
    assert body["docking_results_emitted"] is False
    assert body["external_state_mutated"] is False


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
    assert body["receipt_attach_lane_row_count"] == 0
    assert body["receipt_attach_blocked_lane_count"] == 0
    assert body["receipt_attach_primary_blocked_lane_row"] == {}
    assert body["receipt_attach_lane_rows"] == []
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
            "rows": [
                {
                    "lane_id": "vina_gnina_same_input_scores",
                    "status": "blocked",
                    "ready": False,
                    "blocker": "vina_gnina_same_input_score_evidence_missing",
                    "source_artifact": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
                    "operator_csv": (
                        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                    ),
                    "row_count": 16,
                    "pending_value_count": 32,
                    "pending_metadata_count": 128,
                    "pending_license_count": 16,
                    "pending_approval_token_count": 16,
                    "approval_token_required": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                    ),
                    "next_required_step": "Fill every Vina/GNINA same-input score template row.",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "lane_id": "metric_source_receipt_rows",
                    "status": "blocked",
                    "ready": False,
                    "blocker": "benchmark_metric_source_receipt_rows_unapproved",
                    "source_artifact": (
                        "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
                    ),
                    "operator_csv": (
                        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
                    ),
                    "row_count": 51,
                    "pending_value_count": 510,
                    "pending_metadata_count": 510,
                    "pending_license_count": 0,
                    "pending_approval_token_count": 51,
                    "approval_token_required": (
                        "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
                    ),
                    "next_required_step": (
                        "Fill reviewed metric values, methods, artifact review fields, "
                        "license flags, and approval token for every metric-source receipt row."
                    ),
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
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
    assert body["receipt_attach_lane_row_count"] == 2
    assert body["receipt_attach_blocked_lane_count"] == 2
    assert body["receipt_attach_primary_blocked_lane_row"] == {
        "lane_id": "vina_gnina_same_input_scores",
        "status": "blocked",
        "ready": False,
        "blocker": "vina_gnina_same_input_score_evidence_missing",
        "source_artifact": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
        "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
        "row_count": 16,
        "pending_value_count": 32,
        "pending_metadata_count": 128,
        "pending_license_count": 16,
        "pending_approval_token_count": 16,
        "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES",
        "next_required_step": "Fill every Vina/GNINA same-input score template row.",
        "operator_action_required": True,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }
    assert body["receipt_attach_lane_rows"][1]["lane_id"] == "metric_source_receipt_rows"
    assert body["receipt_attach_lane_rows"][1]["pending_value_count"] == 510
    assert body["receipt_attach_lane_rows"][1]["claim_promotion_allowed"] is False
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
