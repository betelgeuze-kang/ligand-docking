from __future__ import annotations

from tools.product.build_product_production_ai_promotion_workbench import (
    _read_json,
    build_product_production_ai_promotion_workbench,
)


def test_product_production_ai_promotion_workbench_surfaces_blocked_ladder_without_execution() -> None:
    payload = build_product_production_ai_promotion_workbench(
        checkpoint_readiness_packet=_read_json("runs/product_production_ai_checkpoint_readiness_current.json")
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_production_ai_promotion_workbench"
    assert summary["promotion_workbench_ready"] is True
    assert summary["production_ai_promotion_ready"] is False
    assert summary["production_ai_checkpoint_ready"] is False
    assert summary["default_residual_mode"] == "shadow"
    assert summary["trained_model_checkpoint_count"] == 0
    assert summary["gpu_handoff_ready"] is True
    assert summary["gpu_return_receipt_ready"] is True
    assert summary["gpu_receipt_expected_queue_rows"] == 0
    assert summary["gpu_receipt_manifest_identity_row_count"] == 0
    assert summary["post_return_promotion_ladder_stage_count"] == 10
    assert summary["post_return_promotion_ladder_blocked_stage_count"] == 2
    assert summary["blocked_stage_ids"] == ["residual_model_registry", "product_goal_completion_audit"]
    assert summary["ready_key_alias_used_count"] == 2
    assert summary["ready_key_alias_used_stage_ids"] == [
        "production_score_model",
        "production_checkpoint_preflight",
    ]
    assert summary["first_blocked_stage_id"] == "residual_model_registry"
    assert summary["first_blocked_stage_ready_key"] == "production_promotion_allowed"
    assert summary["registry_promotion_missing_gate_ids"] == [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
        "trained_model_checkpoint_count_positive",
    ]
    assert summary["registry_promotion_missing_gate_count"] == 4
    assert summary["registry_promotion_upstream_acceptance_ready"] is True
    assert summary["registry_promotion_currently_satisfied"] is False
    assert "Register or promote a trained preflight-ready production checkpoint" in summary["next_required_step"]
    assert "trained_model_checkpoint_count_positive" in summary["next_required_step"]
    assert "generate_ligand_trajectory_engine.py" in summary["force_gpu_worker_full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in summary[
        "force_gpu_worker_post_return_validation_command"
    ]
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["model_promoted"] is False
    assert summary["external_state_mutated"] is False
    assert len(payload["rows"]) == 10
    assert len(payload["blockers"]) == 2
    assert payload["rows"][0]["artifact"] == "runs/residual_force_gpu_worker_return_receipt_current.json"
    assert payload["rows"][0]["observed_value"] is True
    rows_by_stage = {row["stage_id"]: row for row in payload["rows"]}
    assert rows_by_stage["production_score_model"]["ready_key"] == "score_model_production_checkpoint_ready"
    assert rows_by_stage["production_score_model"]["observed_ready_key"] == "production_checkpoint_ready"
    assert rows_by_stage["production_score_model"]["ready_key_alias_used"] is True
    assert rows_by_stage["production_score_model"]["observed_value"] is True
    assert rows_by_stage["production_checkpoint_preflight"]["observed_ready_key"] == "preflight_green"
    assert rows_by_stage["production_checkpoint_preflight"]["ready_key_alias_used"] is True
    assert rows_by_stage["production_checkpoint_preflight"]["observed_value"] is True
    assert "Register or promote a trained preflight-ready production checkpoint" in rows_by_stage[
        "residual_model_registry"
    ]["next_action"]
