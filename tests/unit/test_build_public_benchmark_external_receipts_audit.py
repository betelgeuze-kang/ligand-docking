from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_external_receipts_audit as mod


def _write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}), encoding="utf-8")


def _write_receipt_csv(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["template_id", "metric_value"])
        writer.writeheader()
        for index in range(rows):
            writer.writerow({"template_id": f"template_{index:03d}", "metric_value": ""})


def _write_inputs(
    tmp_path: Path,
    *,
    comparison_ready: bool,
    receipt_ready: bool,
) -> dict[str, Path]:
    paths = {
        "materialization": tmp_path / "runs/pdbbind_casf_pose_affinity_materialization_manifest_current.json",
        "results": tmp_path / "runs/pdbbind_casf_pose_affinity_results_current.json",
        "phase2": tmp_path / "runs/public_benchmark_phase2_harness_audit_current.json",
        "provenance": tmp_path / "runs/pdbbind_casf_pose_affinity_result_provenance_current.json",
        "scorecard": tmp_path / "runs/pdbbind_casf_pose_affinity_scorecard_current.json",
        "receipt": (
            tmp_path
            / "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
        ),
        "receipt_csv": (
            tmp_path
            / "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
        ),
        "ledger": tmp_path / "runs/benchmark_ledger_current.json",
        "work_order": tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
        "score_template_receipt": (
            tmp_path / "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
        ),
        "execution_preflight": (
            tmp_path / "runs/public_benchmark_vina_gnina_execution_preflight_current.json"
        ),
    }
    _write_summary(
        paths["materialization"],
        {
            "status": "public_benchmark_materialization_ready",
            "operator_input_artifacts": "data/public_benchmarks/pdbbind_casf_pose_affinity",
            "operator_output_artifacts": "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv",
        },
    )
    _write_summary(
        paths["results"],
        {
            "status": "pdbbind_casf_pose_affinity_results_ready",
            "pose_count": 16,
            "replay_pose_count": 16,
            "subset_identity_sha256": "abc123",
            "download_executed": False,
            "prediction_generation_enabled": False,
            "symmetry_aware_ligand_rmsd_ready": True,
            "pose_success_rmsd_threshold_A": 2,
            "top1_mean_rmsd_A": 0.17,
            "top5_best_mean_rmsd_A": 0.17,
            "pose_success_rate": 1.0,
            "top1_pose_success_rate": 1.0,
            "top5_pose_success_rate": 1.0,
            "posebusters_style_validity_checks_ready": True,
            "posebusters_assessed_pose_count": 16,
            "posebusters_valid_rate": 1.0,
            "vina_gnina_comparison_adapter_contract_ready": True,
            "vina_gnina_comparison_adapter_score_evidence_ready": comparison_ready,
            "comparison_adapter_same_input_row_count_match": comparison_ready,
            "vina_gnina_comparison_adapter_status": "comparison_ready" if comparison_ready else "score_missing",
        },
    )
    _write_summary(
        paths["phase2"],
        {"status": "public_benchmark_phase2_harness_audit_ready", "phase2_harness_audit_ready": True},
    )
    _write_summary(paths["provenance"], {"status": "public_benchmark_result_provenance_ready"})
    _write_summary(paths["scorecard"], {"status": "public_benchmark_suite_scorecard_pass"})
    receipt_rows = 2 if receipt_ready else 51
    _write_summary(
        paths["receipt"],
        {
            "status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
                if receipt_ready
                else "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "row_count": receipt_rows,
            "blocked_row_count": 0 if receipt_ready else receipt_rows,
            "receipt_manual_field_pending_count": 0 if receipt_ready else receipt_rows * 10,
            "receipt_approval_token_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_metric_value_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_method_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_input_artifacts_reviewed_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_input_artifact_sha256s_reviewed_pending_count": (
                0 if receipt_ready else receipt_rows
            ),
            "receipt_metric_source_artifact_reviewed_pending_count": (
                0 if receipt_ready else receipt_rows
            ),
            "receipt_payload_schema_reviewed_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_license_ok_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_operator_id_pending_count": 0 if receipt_ready else receipt_rows,
            "receipt_reviewed_at_utc_pending_count": 0 if receipt_ready else receipt_rows,
            "approval_token_required": "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS",
            "claim_promotion_allowed": receipt_ready,
        },
    )
    _write_receipt_csv(paths["receipt_csv"], receipt_rows)
    _write_summary(
        paths["ledger"],
        {
            "schema_version": "benchmark_claim_ledger_v1",
            "entry_count": 4,
            "external_safe_count": 2,
            "locked_or_reject_count": 2,
        },
    )
    _write_summary(
        paths["work_order"],
        {
            "status": "public_benchmark_vina_gnina_comparison_work_order_ready",
            "work_order_ready": True,
            "same_input_score_template_ready": True,
            "score_template_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            "score_template_row_count": 16,
            "score_template_validation_ready": comparison_ready,
            "score_template_filled_score_row_count": 16 if comparison_ready else 0,
            "score_value_pending_count": 0 if comparison_ready else 32,
            "invalid_score_value_count": 0,
            "operator_metadata_pending_count": 0 if comparison_ready else 32,
            "operator_placeholder_pending_count": 0 if comparison_ready else 96,
            "license_ok_pending_count": 0 if comparison_ready else 16,
            "approval_token_pending_count": 0 if comparison_ready else 16,
            "pending_field_count": 0 if comparison_ready else 192,
            "pending_field_counts": {}
            if comparison_ready
            else {
                "approval_token": 16,
                "comparison_score_artifact_path": 16,
                "comparison_score_artifact_sha256": 16,
                "comparison_score_source": 16,
                "gnina_score": 16,
                "license_ok": 16,
                "operator_engine_versions": 16,
                "operator_id": 16,
                "operator_method": 16,
                "operator_prep_policy_sha256": 16,
                "operator_reviewed_at_utc": 16,
                "vina_score": 16,
            },
            "score_template_blocker_count": 0 if comparison_ready else 5,
            "score_template_blockers": []
            if comparison_ready
            else [
                "same_input_score_values_pending",
                "operator_score_metadata_pending",
                "operator_score_placeholders_unfilled",
                "license_ok_pending",
                "approval_token_pending",
            ],
            "adapter_command_after_fill": (
                "python3 tools/build_pdbbind_casf_pose_affinity_results.py "
                "--comparison-scores-csv runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
            ),
            "next_required_step": "Fill Vina/GNINA same-input scores.",
        },
    )
    _write_summary(
        paths["score_template_receipt"],
        {
            "status": "public_benchmark_vina_gnina_score_template_receipt_ready"
            if comparison_ready
            else "blocked_public_benchmark_vina_gnina_score_template_receipt",
            "score_template_receipt_ready": comparison_ready,
            "score_template_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            "score_template_row_count": 16,
            "score_template_validation_ready": comparison_ready,
            "score_template_filled_score_row_count": 16 if comparison_ready else 0,
            "score_value_pending_count": 0 if comparison_ready else 32,
            "invalid_score_value_count": 0,
            "operator_metadata_pending_count": 0 if comparison_ready else 32,
            "operator_placeholder_pending_count": 0 if comparison_ready else 96,
            "license_ok_pending_count": 0 if comparison_ready else 16,
            "approval_token_pending_count": 0 if comparison_ready else 16,
            "pending_field_count": 0 if comparison_ready else 192,
            "pending_field_counts": {}
            if comparison_ready
            else {
                "approval_token": 16,
                "comparison_score_artifact_path": 16,
                "comparison_score_artifact_sha256": 16,
                "comparison_score_source": 16,
                "gnina_score": 16,
                "license_ok": 16,
                "operator_engine_versions": 16,
                "operator_id": 16,
                "operator_method": 16,
                "operator_prep_policy_sha256": 16,
                "operator_reviewed_at_utc": 16,
                "vina_score": 16,
            },
            "score_template_blocker_count": 0 if comparison_ready else 5,
            "score_template_blockers": []
            if comparison_ready
            else [
                "same_input_score_values_pending",
                "operator_score_metadata_pending",
                "operator_score_placeholders_unfilled",
                "license_ok_pending",
                "approval_token_pending",
            ],
            "next_required_step": "Fill Vina/GNINA same-input scores.",
        },
    )
    _write_summary(
        paths["execution_preflight"],
        {
            "status": "public_benchmark_vina_gnina_execution_preflight_ready"
            if comparison_ready
            else "blocked_public_benchmark_vina_gnina_execution_preflight",
            "execution_preflight_ready": comparison_ready,
            "score_template_row_count": 16,
            "ready_for_local_same_input_scoring_row_count": 16 if comparison_ready else 0,
            "blocked_for_local_same_input_scoring_row_count": 0 if comparison_ready else 16,
            "vina_binary_present": comparison_ready,
            "gnina_binary_present": comparison_ready,
            "blockers": [] if comparison_ready else ["vina_binary_missing", "gnina_binary_missing"],
        },
    )
    return paths


def _build(tmp_path: Path, *, comparison_ready: bool, receipt_ready: bool) -> dict:
    paths = _write_inputs(tmp_path, comparison_ready=comparison_ready, receipt_ready=receipt_ready)
    return mod.build_public_benchmark_external_receipts_audit(
        materialization_json=paths["materialization"],
        results_json=paths["results"],
        phase2_audit_json=paths["phase2"],
        provenance_json=paths["provenance"],
        scorecard_json=paths["scorecard"],
        receipt_json=paths["receipt"],
        receipt_csv=paths["receipt_csv"],
        benchmark_ledger_json=paths["ledger"],
        vina_gnina_work_order_json=paths["work_order"],
        vina_gnina_score_template_receipt_json=paths["score_template_receipt"],
        vina_gnina_execution_preflight_json=paths["execution_preflight"],
        root=tmp_path,
    )


def test_public_benchmark_external_receipts_audit_blocks_unapproved_receipts(
    tmp_path: Path,
) -> None:
    payload = _build(tmp_path, comparison_ready=False, receipt_ready=False)
    summary = payload["summary"]
    rows = {row["step_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_public_benchmark_external_receipts_audit"
    assert summary["external_benchmark_receipts_ready"] is False
    assert summary["ready_step_count"] == 5
    assert summary["blocked_step_count"] == 2
    assert summary["primary_blocker_id"] == "vina_gnina_same_input_comparison"
    assert summary["receipt_blocked_row_count"] == 51
    assert summary["claim_promotion_allowed"] is False
    assert rows["benchmark_ledger_review"]["ready"] is True
    assert summary["vina_gnina_comparison_work_order_ready"] is True
    assert summary["vina_gnina_score_template_receipt_present"] is True
    assert summary["vina_gnina_score_template_receipt_ready"] is False
    assert summary["vina_gnina_execution_preflight_present"] is True
    assert summary["vina_gnina_execution_preflight_ready"] is False
    assert summary["vina_gnina_execution_preflight_vina_binary_present"] is False
    assert summary["vina_gnina_execution_preflight_gnina_binary_present"] is False
    assert summary["vina_gnina_execution_preflight_blocked_for_local_same_input_scoring_row_count"] == 16
    assert "vina_binary_missing" in summary["vina_gnina_execution_preflight_blockers"]
    assert summary["vina_gnina_score_template_validation_ready"] is False
    assert summary["vina_gnina_score_template_filled_score_row_count"] == 0
    assert summary["vina_gnina_score_value_pending_count"] == 32
    assert summary["vina_gnina_operator_metadata_pending_count"] == 32
    assert summary["vina_gnina_operator_placeholder_pending_count"] == 96
    assert summary["vina_gnina_license_ok_pending_count"] == 16
    assert summary["vina_gnina_approval_token_pending_count"] == 16
    assert summary["vina_gnina_pending_field_count"] == 192
    assert summary["vina_gnina_pending_field_counts"]["vina_score"] == 16
    assert summary["vina_gnina_pending_field_counts"]["approval_token"] == 16
    assert summary["vina_gnina_score_template_blocker_count"] == 5
    assert "approval_token_pending" in summary["vina_gnina_score_template_blockers"]
    assert summary["vina_gnina_score_template_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["receipt_attach_packet_ready"] is False
    assert summary["receipt_attach_lane_row_count"] == 2
    assert summary["receipt_attach_blocked_lane_count"] == 2
    assert summary["receipt_attach_primary_blocker_id"] == "vina_gnina_same_input_scores"
    assert summary["receipt_attach_primary_blocker"] == "vina_gnina_same_input_score_evidence_missing"
    assert summary["receipt_attach_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["field_work_order_ready"] is False
    assert summary["field_work_order_row_count"] == 22
    assert summary["field_work_order_pending_field_count"] == 702
    assert summary["field_work_order_primary_lane_id"] == "vina_gnina_same_input_scores"
    assert summary["field_work_order_primary_field_name"] == "approval_token"
    assert summary["field_work_order_primary_pending_row_count"] == 16
    assert summary["field_work_order_primary_required_value"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
    )
    assert summary["field_work_order_primary_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
    )
    assert payload["receipt_attach_lane_rows"][0]["operator_action_required"] is True
    assert payload["receipt_attach_lane_rows"][0]["execution_enabled"] is False
    assert payload["receipt_attach_lane_rows"][0]["external_state_mutated"] is False
    assert payload["receipt_attach_lane_rows"][0]["claim_promotion_allowed"] is False
    assert payload["field_work_order_rows"][0]["field_name"] == "approval_token"
    assert payload["field_work_order_rows"][0]["pending_row_count"] == 16
    assert payload["field_work_order_rows"][0]["execution_enabled"] is False
    assert payload["field_work_order_rows"][0]["external_state_mutated"] is False
    assert payload["field_work_order_rows"][0]["claim_promotion_allowed"] is False
    assert payload["field_work_order_rows"][-1]["lane_id"] == "metric_source_receipt_rows"
    assert payload["field_work_order_rows"][-1]["field_name"] == "approval_token"
    assert rows["vina_gnina_same_input_comparison"]["blocker"] == (
        "vina_gnina_same_input_score_evidence_missing"
    )
    assert rows["benchmark_receipt_attach"]["blocker"] == "benchmark_metric_source_receipt_rows_unapproved"
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_public_benchmark_external_receipts_audit_ready_when_all_steps_pass(
    tmp_path: Path,
) -> None:
    payload = _build(tmp_path, comparison_ready=True, receipt_ready=True)
    summary = payload["summary"]

    assert summary["status"] == "public_benchmark_external_receipts_audit_ready"
    assert summary["external_benchmark_receipts_ready"] is True
    assert summary["ready_step_count"] == 7
    assert summary["blocked_step_count"] == 0
    assert summary["blockers"] == []
    assert summary["vina_gnina_score_template_validation_ready"] is True
    assert summary["vina_gnina_score_template_receipt_ready"] is True
    assert summary["vina_gnina_execution_preflight_ready"] is True
    assert summary["vina_gnina_execution_preflight_ready_for_local_same_input_scoring_row_count"] == 16
    assert summary["vina_gnina_score_value_pending_count"] == 0
    assert summary["vina_gnina_pending_field_count"] == 0
    assert summary["receipt_blocked_row_count"] == 0
    assert summary["receipt_attach_packet_ready"] is True
    assert summary["receipt_attach_blocked_lane_count"] == 0
    assert summary["field_work_order_ready"] is True
    assert summary["field_work_order_row_count"] == 0
    assert payload["receipt_attach_lane_rows"][0]["ready"] is True
    assert payload["field_work_order_rows"] == []
    assert summary["claim_promotion_allowed"] is False


def test_public_benchmark_external_receipts_audit_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, comparison_ready=False, receipt_ready=False)
    out_json = tmp_path / "runs/public_benchmark_external_receipts_audit_current.json"
    out_csv = tmp_path / "runs/public_benchmark_external_receipts_audit_current.csv"
    out_md = tmp_path / "runs/public_benchmark_external_receipts_audit_current.md"

    assert mod.main(
        [
            "--materialization-json",
            str(paths["materialization"]),
            "--results-json",
            str(paths["results"]),
            "--phase2-audit-json",
            str(paths["phase2"]),
            "--provenance-json",
            str(paths["provenance"]),
            "--scorecard-json",
            str(paths["scorecard"]),
            "--receipt-json",
            str(paths["receipt"]),
            "--receipt-csv",
            str(paths["receipt_csv"]),
            "--benchmark-ledger-json",
            str(paths["ledger"]),
            "--vina-gnina-work-order-json",
            str(paths["work_order"]),
            "--vina-gnina-score-template-receipt-json",
            str(paths["score_template_receipt"]),
            "--vina-gnina-execution-preflight-json",
            str(paths["execution_preflight"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["summary"]["status"] == "blocked_public_benchmark_external_receipts_audit"
    assert written["summary"]["field_work_order_row_count"] == 22
    assert written["field_work_order_rows"][0]["field_name"] == "approval_token"
    assert "vina_gnina_same_input_comparison" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Public Benchmark External Receipts Audit" in md
    assert "Receipt Attach Lanes" in md
    assert "Field Work Order" in md
