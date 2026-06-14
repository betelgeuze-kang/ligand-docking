from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_priority_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _action_board(path: Path) -> None:
    rows = [
        {
            "blocker_id": blocker_id,
            "current_status": "blocked",
            "required_evidence": f"required evidence for {blocker_id}",
            "owner_action": f"operator action for {blocker_id}",
            "gate_or_artifact": "runs/engine_refinement_tier_readiness_current.json",
            "external_dependency": "operator curated evidence",
            "claim_boundary": "claim remains blocked",
            "blocking_signals": "unit_blocker",
            "next_required_step": f"next step for {blocker_id}",
        }
        for blocker_id in mod.REQUIRED_BLOCKERS
    ]
    _write_csv(
        path,
        rows,
        [
            "blocker_id",
            "current_status",
            "required_evidence",
            "owner_action",
            "gate_or_artifact",
            "external_dependency",
            "claim_boundary",
            "blocking_signals",
            "next_required_step",
        ],
    )


def _receipt(path: Path, *, ready: bool) -> None:
    rows = []
    for blocker_id in mod.REQUIRED_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[blocker_id]
        rows.append(
            {
                "blocker_id": blocker_id,
                "row_status": "pass" if ready else "blocked",
                "blockers": "" if ready else "operator_placeholders_unfilled",
                "evidence_artifact": f"runs/{blocker_id}.json" if ready else "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "expected_evidence_status": expected["status"],
                "observed_evidence_status": expected["status"] if ready else "missing",
                "missing_true_fields": "" if ready else ";".join(expected["true_fields"]),
                "external_state_mutated": False,
            }
        )
    _write_json(
        path,
        {
            "summary": {
                "status": (
                    "engine_refinement_claim_evidence_receipt_ready"
                    if ready
                    else "blocked_engine_refinement_claim_evidence_receipt"
                ),
                "claim_promotion_evidence_receipt_ready": ready,
                "blocked_row_count": 0 if ready else 6,
            },
            "rows": rows,
        },
    )


def _work_order(path: Path) -> None:
    rows = [
        {
            "work_order_id": f"refine_tier_public_benchmark_fill_{index:03d}",
            "target_input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
            "template_row_index": index,
        }
        for index in range(1, 9)
    ]
    _write_csv(path, rows, ["work_order_id", "target_input_csv", "template_row_index"])


def test_engine_refinement_claim_evidence_priority_packet_blocks_current_r9_work() -> None:
    payload = mod.build_engine_refinement_claim_evidence_priority_packet()
    summary = payload["summary"]

    assert summary["status"] == "blocked_engine_refinement_claim_evidence_priority_packet"
    assert summary["priority_packet_ready"] is True
    assert summary["claim_promotion_allowed"] is False
    assert summary["priority_item_count"] == 6
    assert summary["operator_input_required_count"] == 6
    assert summary["blocked_priority_item_count"] == 6
    assert summary["public_benchmark_gate_ready"] is False
    assert summary["public_benchmark_work_order_present"] is True
    assert summary["public_benchmark_work_order_row_count"] == 8
    assert summary["public_benchmark_work_order_apply_ready"] is False
    assert summary["public_benchmark_work_order_apply_blocked_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_ready"] is True
    assert summary["public_benchmark_materialized_apply_ready"] is True
    assert summary["public_benchmark_materialized_candidate_ready"] is True
    assert summary["public_benchmark_materialized_work_order_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_pass_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_blocked_row_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_pair_count"] == 8
    assert summary["public_benchmark_materialized_free_energy_spearman"] == 0.6190476190476191
    assert summary["public_benchmark_materialized_free_energy_spearman_gate_ready"] is True
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p05"] == -0.14285714285714285
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blocker_count"] == 3
    assert summary["public_benchmark_claim_grade_gap_audit_present"] is True
    assert summary["public_benchmark_claim_grade_gap_audit_ready"] is True
    assert summary["public_benchmark_claim_grade_gap_audit_status"] == (
        "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
    )
    assert summary["public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count"] == 8
    assert summary["public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count"] == 3
    assert summary["public_benchmark_claim_grade_gap_audit_minimum_new_pair_count"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count"] == 0
    assert summary["public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count"] == 17
    assert summary["public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count"] == 0
    assert summary["public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count"] == 51
    assert summary["public_benchmark_claim_grade_gap_audit_gap_row_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_blocked_gap_row_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_blocker_count"] == 5
    assert summary["public_benchmark_claim_grade_gap_audit_top_science_gap_id"] == (
        "coordinate_fetch_r4_approval_required"
    )
    assert summary["public_benchmark_claim_grade_gap_audit_top_statistical_gap_id"] == (
        "claim_grade_public_benchmark_pair_count_below_minimum"
    )
    assert summary["public_benchmark_statistical_support_work_order_present"] is True
    assert summary["public_benchmark_statistical_support_work_order_ready"] is True
    assert summary["public_benchmark_statistical_support_work_order_status"] == (
        "refine_tier_public_benchmark_statistical_support_work_order_ready"
    )
    assert summary["public_benchmark_statistical_support_work_order_expansion_slot_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_pair_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count"] == 5
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count"] == 12
    assert summary["public_benchmark_statistical_support_work_order_bootstrap_spearman_p05_deficit"] == (
        0.6428571428571428
    )
    assert summary["public_benchmark_statistical_support_work_order_bootstrap_retest_required"] is True
    assert (
        summary["public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed"]
        is False
    )
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_present"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
    )
    assert summary["public_benchmark_statistical_support_metric_materialization_row_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_ready_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready"] is False
    assert summary["public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"] == 34
    assert summary["public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"] == 17
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count"
        ]
        == 17
    )
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads"
    ] == "dockq;lddt_pli;internal_deltaG"
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count"
    ] == 11
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields"
    ] == (
        "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
        "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
    )
    assert summary["public_benchmark_statistical_support_coordinate_intake_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_intake_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count"
    ] == 0
    assert summary["public_benchmark_statistical_support_coordinate_intake_missing_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
    ] == 136
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_metric_source_templates_present"] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
    )
    assert summary["public_benchmark_statistical_support_metric_source_templates_template_row_count"] == 51
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
        ]
        == 51
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count"] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count"
    ] == 51
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_download_executed"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert summary["top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["top_priority_bucket"] == "public_benchmark_work_order_apply_required"
    assert summary["top_required_input"] == "runs/refine_tier_public_benchmark_work_order_current.csv"
    assert "apply_refine_tier_public_benchmark_work_order.py" in summary["top_verification_command"]
    assert "Review the R4 coordinate-fetch preflight" in summary["top_next_operator_step"]
    assert "r4_ready_for_review_row_count=17" in summary["top_next_operator_step"]
    assert "approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD" in summary[
        "top_next_operator_step"
    ]
    assert "required_input_artifacts=34/17/17" in summary["top_next_operator_step"]
    assert "local_coordinate_path_candidates=136" in summary["top_next_operator_step"]
    assert "local_coordinate_present_targets=0" in summary["top_next_operator_step"]
    assert "local_coordinate_missing_targets=17" in summary["top_next_operator_step"]
    assert "planned_metric_source_payload_count=51" in summary["top_next_operator_step"]
    assert "before any R9 claim receipt or canonical intake promotion" in summary[
        "top_next_operator_step"
    ]
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert "operator_evidence_rows_pending" in summary["blockers"]
    assert payload["rows"][0]["blocker_id"] == "public_benchmark_gate_not_ready"
    assert payload["rows"][0]["operator_input_required"] is True
    assert payload["rows"][0]["public_benchmark_materialized_candidate_ready"] is True
    assert payload["rows"][0]["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert payload["rows"][0]["public_benchmark_claim_grade_gap_audit_ready"] is True
    assert payload["rows"][0]["public_benchmark_claim_grade_gap_audit_blocked_gap_row_count"] == 5
    assert (
        payload["rows"][0]["public_benchmark_claim_grade_gap_audit_top_science_gap_id"]
        == "coordinate_fetch_r4_approval_required"
    )
    assert payload["rows"][0]["public_benchmark_statistical_support_work_order_expansion_slot_count"] == 17
    assert payload["rows"][0][
        "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"
    ] == 17
    assert payload["rows"][0][
        "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"
    ] == 17
    assert payload["rows"][0][
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
    ] == 136
    assert payload["rows"][0][
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
    ] == 0
    assert payload["rows"][0][
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
    ] == 17
    assert payload["rows"][0][
        "public_benchmark_statistical_support_metric_source_templates_ready"
    ] is True
    assert payload["rows"][0][
        "public_benchmark_statistical_support_metric_source_templates_template_row_count"
    ] == 51
    assert payload["rows"][0][
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    ] is True
    assert payload["rows"][0][
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count"
    ] == 17
    assert "Review the R4 coordinate-fetch preflight" in payload["rows"][0][
        "next_operator_step"
    ]
    assert payload["rows"][1]["priority_bucket"] == "blocked_until_public_benchmark_ready"
    assert payload["rows"][1]["prerequisite_blocker_id"] == "public_benchmark_gate_not_ready"
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_engine_refinement_claim_evidence_priority_packet_ready_with_verified_local_receipts(
    tmp_path: Path,
) -> None:
    action_board = tmp_path / "runs" / "action_board.csv"
    receipt = tmp_path / "runs" / "receipt.json"
    public_readiness = tmp_path / "runs" / "public_readiness.json"
    work_order = tmp_path / "runs" / "work_order.csv"
    work_order_apply = tmp_path / "runs" / "work_order_apply.json"
    _action_board(action_board)
    _receipt(receipt, ready=True)
    _write_json(
        public_readiness,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_ready",
                "claim_grade_public_benchmark_ready": True,
            }
        },
    )
    _work_order(work_order)
    _write_json(
        work_order_apply,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_work_order_apply_ready",
                "apply_ready": True,
                "blocked_row_count": 0,
            }
        },
    )

    payload = mod.build_engine_refinement_claim_evidence_priority_packet(
        action_board_csv=action_board.relative_to(tmp_path),
        receipt_json=receipt.relative_to(tmp_path),
        public_benchmark_readiness_json=public_readiness.relative_to(tmp_path),
        public_benchmark_work_order_csv=work_order.relative_to(tmp_path),
        public_benchmark_work_order_apply_json=work_order_apply.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "engine_refinement_claim_evidence_priority_packet_ready"
    assert summary["priority_packet_ready"] is True
    assert summary["claim_evidence_receipt_ready"] is True
    assert summary["operator_input_required_count"] == 0
    assert summary["blocked_priority_item_count"] == 0
    assert summary["public_benchmark_gate_ready"] is True
    assert summary["public_benchmark_work_order_apply_ready"] is True
    assert summary["public_benchmark_statistical_support_work_order_present"] is False
    assert summary["public_benchmark_statistical_support_work_order_ready"] is False
    assert summary["top_priority_bucket"] == "receipt_verified"
    assert summary["blockers"] == []
    assert all(row["priority_bucket"] == "receipt_verified" for row in payload["rows"])


def test_engine_refinement_claim_evidence_priority_packet_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_engine_refinement_claim_evidence_priority_packet"
    assert "priority_bucket" in out_csv.read_text(encoding="utf-8")
    assert "Engine Refinement Claim Evidence Priority Packet" in out_md.read_text(encoding="utf-8")
