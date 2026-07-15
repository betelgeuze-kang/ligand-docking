from __future__ import annotations

import hashlib
import json
from pathlib import Path

from api.result_manifest import write_result_manifest
from api.validated_runner_execution_evidence import (
    EXECUTION_EVIDENCE_PROVENANCE_KEY,
    tier_alpha_adrb2_execution_evidence,
)
from api.validated_runner_runtime_qualification import RECEIPT_SCHEMA_VERSION
from tools.product import build_product_release_source_of_truth_gate as source_gate
from tools.product import run_product_release_current_refresh as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _source_of_truth_ready() -> dict:
    spec = next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "product_release_source_of_truth_gate"
    )
    return {
        "summary": {
            "status": "product_release_source_of_truth_gate_ready",
            "release_source_of_truth_ready": True,
            "blocker_count": 0,
            "stale_artifact_count": 0,
            "readme_drift_count": 0,
            **dict(spec.get("required_int_exact_fields", {})),
        }
    }


def _goal_release_decision_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "goal_release_decision_gate"
    )


def _quality_gate_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "product_quality_gate_verification"
    )


def _quality_gate_ready() -> dict:
    spec = _quality_gate_spec()
    return {
        "summary": {
            "status": spec["required_status"],
            **{field: True for field in spec.get("required_true_fields", [])},
            **{field: 0 for field in spec.get("required_zero_fields", [])},
            **dict(spec.get("required_int_exact_fields", {})),
            **dict(spec.get("required_text_exact_fields", {})),
        }
    }


def _goal_operator_action_board_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "goal_operator_action_board"
    )


def _release_decision_ready(*, bottleneck_recorded: bool = True) -> dict:
    spec = _goal_release_decision_spec()
    summary = {
        "status": spec["required_status"],
        **{field: True for field in spec.get("required_true_fields", [])},
        **{field: 0 for field in spec.get("required_zero_fields", [])},
        **dict(spec.get("required_int_exact_fields", {})),
        **dict(spec.get("required_int_min_fields", {})),
        **dict(spec.get("required_text_exact_fields", {})),
    }
    summary["goal_bottleneck_briefing_full_commercial_receipts_recorded"] = bottleneck_recorded
    return {
        "summary": summary
    }


def _action_board_ready() -> dict:
    spec = _goal_operator_action_board_spec()
    summary = {
        "status": spec["required_status"],
        **{field: True for field in spec.get("required_true_fields", [])},
        **{field: 0 for field in spec.get("required_zero_fields", [])},
        **dict(spec.get("required_text_exact_fields", {})),
    }
    return {
        "summary": summary
    }


def _action_board_stale_release_echo() -> dict:
    payload = _action_board_ready()
    payload["summary"].update(
        {
            "goal_release_decision_gate_status": "blocked_goal_release_decision",
            "goal_release_allowed": False,
            "goal_release_blocker_count": 1,
        }
    )
    return payload


def test_refresh_final_gate_requires_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "product_release_current_refresh_verified"
    assert summary["final_gate_verification_ready"] is True
    assert summary["final_gate_blocker_count"] == 0
    assert summary["final_gate_count"] == 4
    assert decision_row["status"] == "pass"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "required_true_fields"
    ]
    assert decision_row["required_int_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count"
    ] == 2
    assert "product_pose_sampling_readiness_recorded" in decision_row["required_true_fields"]
    assert "product_pose_sampling_readiness_docking_results_emitted" in decision_row[
        "required_zero_fields"
    ]
    assert decision_row["required_int_exact_fields"][
        "product_pose_sampling_readiness_pose_count"
    ] == 6
    assert decision_row["required_text_exact_fields"][
        "product_pose_sampling_readiness_status"
    ] == "product_pose_sampling_readiness_ready"
    assert "product_ledger_privacy_scan_recorded" in decision_row["required_true_fields"]
    assert "product_ledger_privacy_scan_leak_count" in decision_row["required_zero_fields"]
    assert decision_row["required_int_min_fields"][
        "product_ledger_privacy_scan_scan_file_count"
    ] == 285
    assert decision_row["required_int_equal_fields"][
        "product_ledger_privacy_scan_pass_count"
    ] == "product_ledger_privacy_scan_scan_file_count"
    assert decision_row["required_text_exact_fields"][
        "product_ledger_privacy_scan_status"
    ] == "product_ledger_privacy_scan_ready"
    assert "refine_tier_public_benchmark_recorded" in decision_row["required_true_fields"]
    assert (
        "refine_tier_public_benchmark_work_order_apply_recorded"
        in decision_row["required_true_fields"]
    )
    assert (
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_required"
        in decision_row["required_true_fields"]
    )
    assert (
        "refine_tier_public_benchmark_claim_grade_public_benchmark_ready"
        in decision_row["required_zero_fields"]
    )
    assert (
        "refine_tier_public_benchmark_work_order_apply_intake_written"
        in decision_row["required_zero_fields"]
    )
    assert decision_row["required_int_exact_fields"][
        "refine_tier_public_benchmark_blocker_count"
    ] == 6
    assert decision_row["required_int_exact_fields"][
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count"
    ] == 8
    assert decision_row["required_int_exact_fields"][
        "refine_tier_public_benchmark_work_order_apply_metric_evidence_blocked_row_count"
    ] == 8
    assert decision_row["required_text_exact_fields"][
        "refine_tier_public_benchmark_status"
    ] == "blocked_refine_tier_public_benchmark_readiness"
    assert decision_row["required_text_exact_fields"][
        "refine_tier_public_benchmark_work_order_apply_status"
    ] == "blocked_refine_tier_public_benchmark_work_order_apply"
    assert decision_row["required_text_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs"
    ] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )
    assert decision_row["required_int_exact_fields"][
        "production_ai_checkpoint_readiness_production_inference_acceptance_ready_stage_count"
    ] == 7
    assert decision_row["required_int_exact_fields"][
        "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_count"
    ] == 1
    assert decision_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_production_inference_acceptance_blocked_stage_ids"
    ] == "registry_guarded_promotion_acceptance"
    assert decision_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_actionable_blocker_stage_id"
    ] == "registry_guarded_promotion_acceptance"
    assert decision_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_actionable_blocker_check_id"
    ] == "registry_customer_facing_promotion_allowed"
    assert decision_row["required_text_exact_fields"][
        "production_ai_checkpoint_readiness_actionable_blocker_artifact"
    ] == "runs/residual_model_registry_current.json"
    assert (
        "production_ai_checkpoint_readiness_candidate_checkpoint_count"
        not in decision_row["required_int_exact_fields"]
    )
    assert decision_row["required_int_min_fields"][
        "production_ai_checkpoint_readiness_candidate_checkpoint_count"
    ] == 1
    assert decision_row["required_int_exact_fields"][
        "production_ai_promotion_workbench_post_return_ladder_ready_stage_count"
    ] == 7
    assert decision_row["required_int_exact_fields"][
        "production_ai_promotion_workbench_post_return_ladder_blocked_stage_count"
    ] == 3
    assert decision_row["required_text_exact_fields"][
        "production_ai_promotion_workbench_blocked_stage_ids"
    ] == "residual_model_registry;product_ai_architecture_gap_closure;product_goal_completion_audit"
    assert decision_row["required_text_exact_fields"][
        "production_ai_promotion_workbench_first_blocked_stage_id"
    ] == "residual_model_registry"
    assert decision_row["required_text_exact_fields"][
        "production_ai_promotion_workbench_first_blocked_stage_artifact"
    ] == "runs/residual_model_registry_current.json"
    assert decision_row["required_text_exact_fields"][
        "production_ai_promotion_workbench_first_blocked_stage_ready_key"
    ] == "production_promotion_allowed"
    assert (
        "production_ai_promotion_workbench_candidate_checkpoint_count"
        not in decision_row["required_int_exact_fields"]
    )
    assert decision_row["required_int_min_fields"][
        "production_ai_promotion_workbench_candidate_checkpoint_count"
    ] == 1


def test_refresh_final_gate_accepts_nonblocking_product_ai_master_gap(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    release_decision = _release_decision_ready()
    release_decision["summary"].update(
        {
            "master_gap_closure_rollup_all_gaps_closed": False,
            "master_gap_closure_rollup_status": "blocked_master_gap_closure_rollup",
            "master_gap_closure_rollup_open_gap_count": 1,
            "master_gap_closure_rollup_closed_gap_count": 8,
            "master_gap_closure_rollup_open_gap_ids_joined": "PRODUCT-AI",
            "master_gap_closure_rollup_current_primary_open_gap_id": "PRODUCT-AI",
            "master_gap_closure_rollup_release_blocker_row_count": 0,
        }
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        release_decision,
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert payload["summary"]["final_gate_verification_ready"] is True
    assert decision_row["status"] == "pass"
    assert "master_gap_closure_rollup_all_gaps_closed" not in decision_row["required_true_fields"]
    assert "master_gap_closure_rollup_open_gap_count" not in decision_row["required_int_exact_fields"]
    assert decision_row["required_int_exact_fields"]["master_gap_closure_rollup_release_blocker_row_count"] == 0


def test_refresh_final_gate_allows_multiple_production_ai_checkpoint_candidates(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    release_decision = _release_decision_ready()
    release_decision["summary"][
        "production_ai_checkpoint_readiness_candidate_checkpoint_count"
    ] = 1462
    release_decision["summary"][
        "production_ai_promotion_workbench_candidate_checkpoint_count"
    ] = 1462
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        release_decision,
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert payload["summary"]["status"] == "product_release_current_refresh_verified"
    assert decision_row["status"] == "pass"
    assert decision_row["failed_int_exact_fields"] == []
    assert decision_row["failed_int_min_fields"] == []


def test_refresh_final_gate_blocks_missing_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(bottleneck_recorded=False),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "missing_true_fields"
    ]


def test_refresh_final_gate_blocks_source_of_truth_coverage_drift(tmp_path: Path) -> None:
    source_payload = _source_of_truth_ready()
    source_payload["summary"]["row_count"] -= 1
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        source_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    source_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "product_release_source_of_truth_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert source_row["status"] == "fail"
    assert source_row["failed_int_exact_fields"] == ["row_count"]


def test_refresh_final_gate_blocks_quality_gate_verification_drift(tmp_path: Path) -> None:
    quality_payload = _quality_gate_ready()
    quality_payload["summary"]["pass_count"] -= 1
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        quality_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    quality_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "product_quality_gate_verification"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert quality_row["status"] == "fail"
    assert quality_row["failed_int_exact_fields"] == ["pass_count"]


def test_refresh_final_gate_blocks_pose_sampling_release_decision_drift(tmp_path: Path) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_pose_sampling_readiness_pose_count"] = 4
    decision_payload["summary"]["product_pose_sampling_readiness_docking_results_emitted"] = True
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["nonzero_fields"] == [
        "product_pose_sampling_readiness_docking_results_emitted"
    ]
    assert decision_row["failed_int_exact_fields"] == [
        "product_pose_sampling_readiness_pose_count"
    ]


def test_refresh_final_gate_blocks_ledger_privacy_scan_release_decision_drift(
    tmp_path: Path,
) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_ledger_privacy_scan_leak_count"] = 1
    decision_payload["summary"]["product_ledger_privacy_scan_scan_file_count"] = 284
    decision_payload["summary"]["product_ledger_privacy_scan_pass_count"] = 284
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["nonzero_fields"] == ["product_ledger_privacy_scan_leak_count"]
    assert decision_row["failed_int_min_fields"] == [
        "product_ledger_privacy_scan_scan_file_count",
        "product_ledger_privacy_scan_pass_count",
    ]
    assert decision_row["failed_int_equal_fields"] == []
    assert decision_row["failed_int_exact_fields"] == []


def test_refresh_final_gate_blocks_refine_tier_public_benchmark_drift(
    tmp_path: Path,
) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"][
        "refine_tier_public_benchmark_work_order_apply_intake_written"
    ] = True
    decision_payload["summary"][
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count"
    ] = 7
    decision_payload["summary"][
        "refine_tier_public_benchmark_status"
    ] = "refine_tier_public_benchmark_ready"
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["nonzero_fields"] == [
        "refine_tier_public_benchmark_work_order_apply_intake_written"
    ]
    assert decision_row["failed_int_exact_fields"] == [
        "refine_tier_public_benchmark_work_order_apply_blocked_row_count"
    ]
    assert decision_row["failed_text_exact_fields"] == [
        "refine_tier_public_benchmark_status"
    ]


def test_refresh_final_gate_blocks_ledger_privacy_scan_pass_count_mismatch(
    tmp_path: Path,
) -> None:
    decision_payload = _release_decision_ready()
    decision_payload["summary"]["product_ledger_privacy_scan_pass_count"] = 286
    decision_payload["summary"]["product_ledger_privacy_scan_scan_file_count"] = 287
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        decision_payload,
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert decision_row["failed_int_min_fields"] == []
    assert decision_row["failed_int_equal_fields"] == [
        "product_ledger_privacy_scan_pass_count"
    ]


def test_refresh_final_gate_blocks_stale_action_board_release_decision_echo(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )
    _write_json(
        tmp_path / "runs" / "product_quality_gate_verification_current.json",
        _quality_gate_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_operator_action_board_current.json",
        _action_board_stale_release_echo(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    action_board_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_operator_action_board"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert action_board_row["status"] == "fail"
    assert action_board_row["missing_true_fields"] == ["goal_release_allowed"]
    assert action_board_row["nonzero_fields"] == ["goal_release_blocker_count"]
    assert action_board_row["failed_text_exact_fields"] == ["goal_release_decision_gate_status"]


def test_run_command_routes_tier_alpha_smoke_in_process(tmp_path: Path, monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_tier_alpha(
        command: str,
        *,
        cwd: Path,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> dict:
        observed["command"] = command
        observed["cwd"] = cwd
        observed["timeout_seconds"] = timeout_seconds
        observed["env"] = env
        return {"returncode": 0, "timed_out": False}

    monkeypatch.setattr(mod, "_run_tier_alpha_smoke_in_process", fake_tier_alpha)

    result = mod._run_command(
        "python3 tools/product/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 420",
        cwd=tmp_path,
        timeout_seconds=450,
    )

    assert result == {"returncode": 0, "timed_out": False}
    assert observed["cwd"] == tmp_path
    assert observed["timeout_seconds"] == 450
    assert observed["env"] is None
    assert str(observed["command"]).endswith("--timeout-seconds 420")


def test_release_refresh_propagates_smoke_result_root_to_following_builders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed_environments: list[dict[str, str]] = []

    def fake_run_command(
        command: str,
        *,
        cwd: Path,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> dict[str, object]:
        del command, cwd, timeout_seconds
        observed_environments.append(dict(env or {}))
        return {"returncode": 0, "timed_out": False}

    monkeypatch.delenv("RESULTS_STORAGE_PATH", raising=False)
    monkeypatch.setenv(
        "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH",
        "/operator/runtime-receipt.json",
    )
    monkeypatch.setattr(mod, "_run_command", fake_run_command)
    workspace = "runs/tier-alpha-custom"

    mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[
            (
                "python3 tools/product/run_tier_alpha_adrb2_dispatch_smoke.py "
                f"--workspace {workspace}"
            ),
            "python3 tools/product/build_restricted_unattended_execution_readiness.py",
        ],
    )

    assert "RESULTS_STORAGE_PATH" not in observed_environments[0]
    assert observed_environments[1]["RESULTS_STORAGE_PATH"] == str(
        tmp_path / workspace / "results"
    )
    assert observed_environments[1][
        "API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH"
    ] == "/operator/runtime-receipt.json"


def test_release_refresh_builds_current_image_preflight_before_restricted_evidence() -> None:
    commands = source_gate.RELEASE_REFRESH_COMMANDS
    image_preflight = "python3 tools/build_product_image_smoke_preflight.py"
    restricted = (
        "python3 tools/product/build_restricted_unattended_execution_readiness.py"
    )

    assert commands.index(
        "python3 tools/product/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 420"
    ) < commands.index(image_preflight)
    assert commands.index(image_preflight) < commands.index(restricted)

    restricted_spec = next(
        spec
        for spec in source_gate.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "restricted_unattended_execution_readiness"
    )
    assert (
        "runs/product_image_smoke_preflight_current.json"
        in restricted_spec["depends_on"]
    )


def test_tier_alpha_smoke_in_process_enforces_parent_timeout(tmp_path: Path) -> None:
    result = mod._run_tier_alpha_smoke_in_process(
        "python3 -c 'import time; time.sleep(30)'",
        cwd=tmp_path,
        timeout_seconds=1,
    )

    assert result["returncode"] != 0
    assert result["timed_out"] is True


def test_tier_alpha_smoke_in_process_recovers_completed_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "runs/tier_alpha_dispatch_smoke/current"
    job_id = "tier_alpha_adrb2_smoke_20260613T000000Z_recovered"
    out_json = tmp_path / "runs/tier_alpha_adrb2_dispatch_smoke_current.json"
    signing_key = "unit-test-operator-managed-recovery-signing-key"
    key_id = "unit-test-recovery-key-2026"
    attempt_dir = (
        workspace
        / "results"
        / job_id
        / ".attempts"
        / f"attempt-000001-{'a' * 64}-{'b' * 64}"
    )
    attempt_dir.mkdir(parents=True)
    result_file = attempt_dir / "htvs_summary.json"
    runner_execution = attempt_dir / "runner_execution.json"
    result_manifest = attempt_dir / "result_manifest.json"
    published_status = attempt_dir / "published_status.json"
    result_file.write_text('{"status":"completed"}\n', encoding="utf-8")
    runner_execution.write_text(
        '{"ok":true,"returncode":0,"timed_out":false,"timeout_seconds":60}\n',
        encoding="utf-8",
    )
    runtime_qualification = {
        "validated_runner_namespace_runtime_qualified": True,
        "validated_runner_namespace_runtime_receipt_schema_version": (
            RECEIPT_SCHEMA_VERSION
        ),
        "validated_runner_namespace_runtime_receipt_sha256": "c" * 64,
        "validated_runner_namespace_runtime_receipt_issued_at_utc": (
            "2026-07-16T00:00:00Z"
        ),
        "validated_runner_namespace_runtime_receipt_expires_at_utc": (
            "2026-07-16T01:00:00Z"
        ),
    }
    manifest_payload = write_result_manifest(
        result_manifest,
        job_id=job_id,
        request={"runner_profile_id": "ligand_htvs_pipeline_default"},
        status="completed",
        result_file=str(result_file),
        signing_key=signing_key,
        key_id=key_id,
        worker_provenance={
            "worker_id": "tier-alpha-recovery-worker",
            "attempt_count": 1,
            "attempt_token_sha256": "b" * 64,
            "validated_runner_runtime_qualification": runtime_qualification,
            EXECUTION_EVIDENCE_PROVENANCE_KEY: (
                tier_alpha_adrb2_execution_evidence(job_id)
            ),
        },
    )
    status_payload = {
        "job_id": job_id,
        "status": "completed",
        "result_file": str(result_file),
        "runner_execution": str(runner_execution),
        "result_manifest": str(result_manifest),
        **runtime_qualification,
    }
    published_status.write_text(
        json.dumps(status_payload) + "\n",
        encoding="utf-8",
    )
    evidence = {
        "job_id": job_id,
        "status_path": published_status,
        "status_payload": status_payload,
        "result_file": result_file,
        "runner_execution": runner_execution,
        "runner_payload": {
            "ok": True,
            "returncode": 0,
            "timed_out": False,
            "timeout_seconds": 60,
        },
        "result_manifest": result_manifest,
        "result_manifest_sha256": hashlib.sha256(
            result_manifest.read_bytes()
        ).hexdigest(),
        "manifest_payload": manifest_payload,
        "ledger_payload": {
            "worker_dispatch_enqueued": True,
            "worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
            "simulation_result_file": str(result_file),
            "progress_state": "worker_dispatch_completed",
            "current_step": "worker_dispatch_completed",
        },
    }

    def _verified_scanner(
        observed_workspace: Path,
        *,
        started_at: float,
    ) -> dict:
        assert observed_workspace == workspace
        assert started_at > 0
        return evidence

    monkeypatch.setenv("API_RESULT_MANIFEST_SIGNING_KEY", signing_key)
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", key_id)
    monkeypatch.setattr(
        mod,
        "_latest_completed_tier_alpha_evidence",
        _verified_scanner,
    )
    result = mod._run_tier_alpha_smoke_in_process(
        (
            "python3 -c 'import time; time.sleep(30)' "
            f"--workspace {workspace} --out-json {out_json}"
        ),
        cwd=Path.cwd(),
        timeout_seconds=10,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result["returncode"] == 0
    assert result["timed_out"] is False
    assert result["completed_evidence_recovered"] is True
    assert payload["summary"]["status"] == "tier_alpha_adrb2_dispatch_smoke_pass"
    assert payload["job_id"] == job_id
    assert payload["ledger_worker_state"] == "completed_fail_closed"
    assert payload["simulation_sync_status"] == "completed"
    assert payload["summary"]["validated_result_artifacts_verified"] is True
    assert payload["summary"]["ledger_result_binding_verified"] is True
    assert payload["result_manifest_signature_verified"] is True
    assert payload["result_manifest_status_verified"] is True
    assert payload["result_manifest_sha256"] == evidence[
        "result_manifest_sha256"
    ]


def test_tier_alpha_recovery_rejects_public_default_manifest_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "tier-alpha-default-key"
    results_dir = workspace / "results"
    results_dir.mkdir(parents=True)
    job_id = "tier_alpha_adrb2_smoke_default_key"
    result_file = tmp_path / "default-key-result.json"
    result_file.write_text("{}\n", encoding="utf-8")
    manifest_payload = write_result_manifest(
        tmp_path / "default-key-manifest.json",
        job_id=job_id,
        request={"runner_profile_id": "ligand_htvs_pipeline_default"},
        status="completed",
        result_file=str(result_file),
        signing_key="tier-alpha-local-smoke-signing-key",
        key_id="tier-alpha-local",
    )
    monkeypatch.setenv(
        "API_RESULT_MANIFEST_SIGNING_KEY",
        "tier-alpha-local-smoke-signing-key",
    )
    monkeypatch.setenv("API_RESULT_MANIFEST_KEY_ID", "tier-alpha-local")

    assert (
        mod._verify_tier_alpha_manifest(
            manifest_payload,
            expected_job_id=job_id,
        )
        is False
    )
    assert (
        mod._latest_completed_tier_alpha_evidence(
            workspace,
            started_at=0,
        )
        == {}
    )
