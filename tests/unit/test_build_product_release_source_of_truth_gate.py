from __future__ import annotations

import json
import os
from pathlib import Path

from tools.product import build_product_release_source_of_truth_gate as mod
from tools.product import run_product_release_current_refresh as refresh_mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _accuracy_payload() -> dict:
    return {
        "summary": {
            "status": "green",
            "row_count": 5,
            "pass_row_count": 4,
            "restricted_pass_row_count": 1,
            "blocked_row_count": 0,
            "missing_row_count": 0,
        }
    }


def test_release_source_of_truth_gate_blocks_stale_artifact_and_readme_drift(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "old_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "new_goal_audit"}})
    os.utime(artifact, (1_700_000_000, 1_700_000_000))
    os.utime(dependency, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=5 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["release_source_of_truth_ready"] is False
    assert summary["stale_artifact_count"] == 1
    assert summary["readme_drift_count"] == 1
    assert summary["blocked_artifact_ids"] == ["operator_packet", "readme_accuracy_parity:README.md"]
    stale_row = next(row for row in payload["rows"] if row["artifact_id"] == "operator_packet")
    assert stale_row["stale_dependency_paths"] == ["runs/goal_audit.json"]
    readme_row = next(row for row in payload["rows"] if row["row_type"] == "readme_metric_drift")
    assert "pass=5" in readme_row["obsolete_fragments_present"]


def test_release_source_of_truth_gate_passes_current_artifact_and_readme_metrics(tmp_path: Path) -> None:
    artifact = tmp_path / "runs" / "operator_packet.json"
    dependency = tmp_path / "runs" / "goal_audit.json"
    _write_json(artifact, {"summary": {"status": "current_operator_packet"}})
    _write_json(dependency, {"summary": {"status": "current_goal_audit"}})
    os.utime(dependency, (1_700_000_000, 1_700_000_000))
    os.utime(artifact, (1_700_000_100, 1_700_000_100))

    _write_json(tmp_path / "runs" / "accuracy_parity_scorecard_current.json", _accuracy_payload())
    (tmp_path / "README.md").write_text(
        "runs/accuracy_parity_scorecard_current.json status=green pass=4 restricted_pass=1 blocked=0\n",
        encoding="utf-8",
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[
            {
                "artifact_id": "operator_packet",
                "artifact_path": "runs/operator_packet.json",
                "builder_command": "python3 tools/build_operator_packet.py",
                "depends_on": ["runs/goal_audit.json"],
            }
        ],
        readme_paths=["README.md"],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    assert payload["summary"]["release_source_of_truth_ready"] is True
    assert payload["blockers"] == []


def test_product_release_current_refresh_defaults_to_dry_run_plan(tmp_path: Path) -> None:
    payload = refresh_mod.run_product_release_current_refresh(
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_planned"
    assert payload["summary"]["execute"] is False
    assert payload["summary"]["command_count"] == 1
    assert payload["rows"][0]["executed"] is False
    assert payload["rows"][0]["status"] == "planned"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["verification_rows"] == []


def test_product_release_current_refresh_blocks_if_final_gate_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "blocked_product_release_source_of_truth_gate",
                "release_source_of_truth_ready": False,
                "blocker_count": 1,
                "stale_artifact_count": 1,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}},
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["final_gate_verification_ready"] is False
    assert payload["summary"]["final_gate_blocker_count"] == 1
    assert payload["verification_rows"][0]["gate_id"] == "product_release_source_of_truth_gate"
    assert payload["verification_rows"][0]["status"] == "fail"


def test_product_release_current_refresh_verifies_final_gates_after_execute(tmp_path: Path, monkeypatch) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "product_release_source_of_truth_gate_ready",
                "release_source_of_truth_ready": True,
                "blocker_count": 0,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}},
    )

    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": 0, "timed_out": False},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/build_example.py"],
    )

    assert payload["summary"]["status"] == "product_release_current_refresh_verified"
    assert payload["summary"]["final_gate_verification_ready"] is True
    assert payload["summary"]["final_gate_blocker_count"] == 0


def test_product_release_current_refresh_blocks_timed_out_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        refresh_mod,
        "_run_command",
        lambda command, *, cwd, timeout_seconds: {"returncode": -9, "timed_out": True},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/hangs.py"],
        command_timeout_seconds=7,
    )

    assert payload["summary"]["status"] == "blocked_product_release_current_refresh"
    assert payload["summary"]["timed_out_count"] == 1
    assert payload["summary"]["command_timeout_seconds"] == 7
    assert payload["rows"][0]["status"] == "timeout"
    assert payload["rows"][0]["release_blocker"] is True
    assert payload["verification_rows"] == []


def test_product_release_current_refresh_uses_command_timeout_hint(tmp_path: Path, monkeypatch) -> None:
    observed: list[int] = []

    def fake_run(command: str, *, cwd: Path, timeout_seconds: int) -> dict:
        observed.append(timeout_seconds)
        return {"returncode": 0, "timed_out": False}

    monkeypatch.setattr(refresh_mod, "_run_command", fake_run)
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        {
            "summary": {
                "status": "product_release_source_of_truth_gate_ready",
                "release_source_of_truth_ready": True,
                "blocker_count": 0,
                "stale_artifact_count": 0,
                "readme_drift_count": 0,
            }
        },
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        {"summary": {"status": "goal_release_ready", "release_allowed": True, "blocker_count": 0}},
    )

    payload = refresh_mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=["python3 tools/smoke.py --timeout-seconds 12"],
        command_timeout_seconds=99,
    )

    assert observed == [42]
    assert payload["rows"][0]["timeout_seconds"] == 42
    assert payload["summary"]["status"] == "product_release_current_refresh_verified"


def test_release_source_of_truth_tracks_customer_report_ux_artifacts() -> None:
    artifact_ids = {spec["artifact_id"] for spec in mod.DEFAULT_ARTIFACT_SPECS}
    status_ids = {spec["artifact_id"] for spec in mod.DEFAULT_STATUS_SPECS}

    assert "product_ai_report_explanation_packet" in artifact_ids
    assert "product_ai_report_ux_contract" in artifact_ids
    assert "product_ai_decision_graph_contract" in artifact_ids
    assert "product_execution_work_order" in artifact_ids
    assert "product_execution_preflight" in artifact_ids
    assert "product_ai_report_explanation_packet_semantic_ready" in status_ids
    assert "product_ai_report_ux_contract_semantic_ready" in status_ids
    assert "product_ledger_privacy_scan" in artifact_ids
    assert "api_runner_profile_promotion_operator_receipt" in artifact_ids
    assert "product_launch_r4_preflight" in artifact_ids
    assert "engine_refinement_claim_promotion_action_board" in artifact_ids
    assert "engine_refinement_claim_evidence_receipt" in artifact_ids
    assert "product_scope_breadth_closure_checklist" in artifact_ids
    assert "product_scope_breadth_evidence_receipt" in artifact_ids
    assert "goal_operator_intake_kit" in artifact_ids
    assert "goal_api_surface_contract" in artifact_ids
    assert "goal_bottleneck_briefing" in artifact_ids
    assert "product_full_commercial_blocker_evidence_matrix" in artifact_ids
    assert "product_commercial_readiness_execution_ladder" in artifact_ids
    assert "product_rollout_execution_smoke_receipt" in artifact_ids
    assert "deploy_ops_legal_gap_closure" in artifact_ids
    assert "science_claim_promotion_gap_closure" in artifact_ids
    assert "master_gap_closure_rollup" in artifact_ids
    assert "python3 tools/build_api_runner_profile_promotion_operator_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "product_release_bundle_semantic_ready" in status_ids
    assert "goal_api_surface_contract_semantic_ready" in status_ids
    assert "goal_bottleneck_briefing_semantic_ready" in status_ids
    goal_action_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_operator_action_board"
    )
    assert "runs/product_goal_completion_audit_current.json" in goal_action_spec["depends_on"]
    assert "runs/engine_refinement_claim_promotion_action_board_current.csv" in goal_action_spec["depends_on"]
    goal_audit_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_goal_completion_audit"
    )
    assert "runs/goal_operator_action_board_current.json" not in goal_audit_spec["depends_on"]
    assert "runs/engine_refinement_tier_readiness_current.json" in goal_audit_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in goal_audit_spec["depends_on"]
    scope_closure_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_scope_breadth_closure_checklist"
    )
    assert "runs/transporter_slot_assignment_candidate_workbook_current.json" in scope_closure_spec["depends_on"]
    assert "runs/transporter_manual_review_intake_template_current.json" in scope_closure_spec["depends_on"]
    scope_receipt_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_scope_breadth_evidence_receipt"
    )
    assert "config/product_scope_breadth_evidence_receipt_current.csv" in scope_receipt_spec["depends_on"]
    assert "runs/product_scope_breadth_closure_checklist_current.json" in scope_receipt_spec["depends_on"]
    intake_kit_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_operator_intake_kit"
    )
    assert "runs/goal_operator_action_board_current.json" in intake_kit_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in intake_kit_spec["depends_on"]
    assert "config/product_scope_breadth_evidence_receipt_current.csv" in intake_kit_spec["depends_on"]
    goal_api_surface_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_api_surface_contract"
    )
    assert "api/goal.py" in goal_api_surface_spec["depends_on"]
    assert "api/main.py" in goal_api_surface_spec["depends_on"]
    assert "api/security.py" in goal_api_surface_spec["depends_on"]
    goal_bottleneck_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "goal_bottleneck_briefing"
    )
    assert "runs/product_goal_completion_audit_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_operator_action_board_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_operator_intake_kit_current/manifest.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/product_public_benchmark_work_order_current.json" in goal_bottleneck_spec["depends_on"]
    assert "runs/goal_release_decision_gate_current.json" not in goal_bottleneck_spec["depends_on"]
    assert "runs/product_release_source_of_truth_gate_current.json" not in goal_bottleneck_spec["depends_on"]
    full_commercial_matrix_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_full_commercial_blocker_evidence_matrix"
    )
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/engine_refinement_claim_evidence_receipt_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/product_goal_completion_audit_current.json" in full_commercial_matrix_spec["depends_on"]
    assert "runs/goal_bottleneck_briefing_current.json" in full_commercial_matrix_spec["depends_on"]
    commercial_ladder_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_execution_ladder"
    )
    assert "runs/product_commercial_readiness_operator_packet_current.json" in commercial_ladder_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_operator_packet_freshness_current.json" in commercial_ladder_spec[
        "depends_on"
    ]
    commercial_handoff_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_commercial_readiness_handoff_bundle"
    )
    assert "runs/product_commercial_readiness_operator_packet_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_operator_packet_freshness_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_commercial_readiness_execution_ladder_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in commercial_handoff_spec[
        "depends_on"
    ]
    rollout_smoke_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_rollout_execution_smoke_receipt"
    )
    assert "runs/product_rollout_execution_readiness_current.json" in rollout_smoke_spec["depends_on"]
    registry_spec = next(spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "residual_model_registry")
    assert "runs/residual_shadow_ab_current.json" in registry_spec["depends_on"]
    execution_work_order_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_execution_work_order"
    )
    assert "runs/product_readiness_gate_current.json" in execution_work_order_spec["depends_on"]
    execution_preflight_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_execution_preflight"
    )
    assert "runs/product_execution_work_order_current.json" in execution_preflight_spec["depends_on"]
    decision_graph_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_decision_graph_contract"
    )
    assert "runs/product_ai_report_ux_contract_current.json" in decision_graph_spec["depends_on"]
    explanation_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_report_explanation_packet"
    )
    assert "runs/product_ai_decision_graph_contract_current.json" not in explanation_spec["depends_on"]
    report_ux_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_ai_report_ux_contract"
    )
    assert "runs/product_ai_decision_graph_contract_current.json" not in report_ux_spec["depends_on"]
    deploy_ops_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "deploy_ops_legal_gap_closure"
    )
    assert "runs/product_rollout_execution_smoke_receipt_current.json" in deploy_ops_spec["depends_on"]
    science_claim_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "science_claim_promotion_gap_closure"
    )
    assert "runs/gpcr_conditional_prior_promotion_gate_current.json" in science_claim_spec["depends_on"]
    master_rollup_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "master_gap_closure_rollup"
    )
    assert "runs/science_claim_promotion_gap_closure_current.json" in master_rollup_spec["depends_on"]
    assert "runs/deploy_ops_legal_gap_closure_current.json" in master_rollup_spec["depends_on"]
    privacy_scan_spec = next(
        spec
        for spec in mod.DEFAULT_ARTIFACT_SPECS
        if spec["artifact_id"] == "product_ledger_privacy_scan"
    )
    assert "runs/goal_readiness_rollup_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_operator_action_board_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_operator_intake_kit_current/manifest.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_release_burndown_work_order_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_api_surface_contract_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/goal_bottleneck_briefing_current.json" in privacy_scan_spec["depends_on"]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in privacy_scan_spec["depends_on"]
    release_bundle_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "product_release_bundle"
    )
    assert "runs/product_goal_completion_audit_current.json" in release_bundle_spec["depends_on"]
    assert "runs/engine_refinement_claim_evidence_receipt_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_scope_breadth_evidence_receipt_current.json" in release_bundle_spec["depends_on"]
    assert "runs/product_full_commercial_blocker_evidence_matrix_current.json" in release_bundle_spec[
        "depends_on"
    ]
    evidence_receipt_spec = next(
        spec for spec in mod.DEFAULT_ARTIFACT_SPECS if spec["artifact_id"] == "engine_refinement_claim_evidence_receipt"
    )
    assert "config/engine_refinement_claim_promotion_evidence_receipt_current.csv" in evidence_receipt_spec["depends_on"]
    assert "runs/engine_refinement_claim_promotion_action_board_current.csv" in evidence_receipt_spec["depends_on"]
    assert "product_ledger_privacy_scan_semantic_ready" in status_ids
    assert "python3 tools/build_product_ai_report_explanation_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ai_report_ux_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_residual_shadow_ab.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_execution_work_order.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_execution_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert mod.RELEASE_REFRESH_COMMANDS.count("python3 tools/build_product_ai_decision_graph_contract.py") == 2
    assert "python3 tools/product/build_engine_refinement_tier_readiness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/product/build_product_launch_r4_preflight.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_ledger_privacy_scan.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_scope_breadth_closure_checklist.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_scope_breadth_evidence_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_operator_intake_kit.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_api_surface_contract.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_goal_bottleneck_briefing.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_operator_packet.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_operator_packet_freshness.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_execution_ladder.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_commercial_readiness_handoff_bundle.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_product_rollout_execution_smoke_receipt.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_deploy_ops_legal_gap_closure.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_science_claim_promotion_gap_closure.py" in mod.RELEASE_REFRESH_COMMANDS
    assert "python3 tools/build_master_gap_closure_rollup.py" in mod.RELEASE_REFRESH_COMMANDS
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_closure_checklist.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_scope_breadth_evidence_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 deploy/product_release_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_goal_completion_audit.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_action_board.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_action_board.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_intake_kit.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_operator_intake_kit.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_shadow_ab.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_residual_model_registry.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_work_order.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_preflight.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_execution_preflight.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_capability_surface_contract.py")
    )
    decision_graph_indices = [
        index
        for index, command in enumerate(mod.RELEASE_REFRESH_COMMANDS)
        if command == "python3 tools/build_product_ai_decision_graph_contract.py"
    ]
    assert decision_graph_indices[0] < mod.RELEASE_REFRESH_COMMANDS.index(
        "python3 tools/build_product_ai_report_explanation_packet.py"
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ai_report_ux_contract.py") < (
        decision_graph_indices[1]
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_api_surface_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_api_surface_contract.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_release_decision_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_goal_bottleneck_briefing.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ledger_privacy_scan.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_full_commercial_blocker_evidence_matrix.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet_freshness.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_operator_packet_freshness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_execution_ladder.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_execution_ladder.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_commercial_readiness_handoff_bundle.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_ledger_privacy_scan.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_smoke_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_rollout_execution_smoke_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_deploy_ops_legal_gap_closure.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_deploy_ops_legal_gap_closure.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_science_claim_promotion_gap_closure.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_master_gap_closure_rollup.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_release_source_of_truth_gate.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_tier_readiness.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_claim_evidence_receipt.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_engine_refinement_claim_evidence_receipt.py") < (
        mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/product/build_product_launch_r4_preflight.py")
    )
    assert mod.RELEASE_REFRESH_COMMANDS.index("python3 tools/build_product_goal_completion_audit.py") < (
        max(
            index
            for index, command in enumerate(mod.RELEASE_REFRESH_COMMANDS)
            if command == "python3 deploy/product_release_bundle.py"
        )
    )


def test_release_source_of_truth_blocks_fresh_but_semantically_blocked_report(tmp_path: Path) -> None:
    report = tmp_path / "runs" / "product_ai_report_ux_contract_current.json"
    _write_json(
        report,
        {
            "summary": {
                "status": "blocked_product_ai_report_ux_contract",
                "ai_report_ux_ready": False,
                "customer_report_viewer_binding_ready": False,
            }
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_ai_report_ux_contract_semantic_ready",
                "artifact_path": "runs/product_ai_report_ux_contract_current.json",
                "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
                "required_status": "product_ai_report_ux_contract_ready",
                "required_true_fields": ["ai_report_ux_ready", "customer_report_viewer_binding_ready"],
            }
        ],
        readme_paths=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_release_source_of_truth_gate"
    assert summary["semantic_status_row_count"] == 1
    assert summary["semantic_status_blocker_count"] == 1
    row = payload["rows"][0]
    assert row["row_type"] == "artifact_semantic_status"
    assert row["observed_status"] == "blocked_product_ai_report_ux_contract"
    assert row["missing_true_fields"] == ["ai_report_ux_ready", "customer_report_viewer_binding_ready"]


def test_release_source_of_truth_accepts_top_level_release_bundle_status(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_bundle_current.json",
        {
            "status": "release_bundle_ready_for_operator_review",
            "release_bundle_ready": True,
            "blocker_count": 0,
        },
    )

    payload = mod.build_product_release_source_of_truth_gate(
        root=tmp_path,
        artifact_specs=[],
        status_specs=[
            {
                "artifact_id": "product_release_bundle_semantic_ready",
                "artifact_path": "runs/product_release_bundle_current.json",
                "builder_command": "python3 deploy/product_release_bundle.py",
                "required_status": "release_bundle_ready_for_operator_review",
                "required_true_fields": ["release_bundle_ready"],
            }
        ],
        readme_paths=[],
    )

    assert payload["summary"]["status"] == "product_release_source_of_truth_gate_ready"
    assert payload["summary"]["semantic_status_blocker_count"] == 0
    row = payload["rows"][0]
    assert row["status"] == "pass"
    assert row["observed_status"] == "release_bundle_ready_for_operator_review"
