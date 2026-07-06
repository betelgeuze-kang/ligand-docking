#!/usr/bin/env python3
"""Materialize local contract artifacts needed by api-worker-contract CI."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _bootstrap_repo_root() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def _run(script: str, *args: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    subprocess.run(
        [sys.executable, script, *args],
        cwd=ROOT,
        env=env,
        check=True,
    )


def materialize(*, evidence_dir: str = "/tmp/api_runner_profile_evidence_templates") -> None:
    _bootstrap_repo_root()
    from tools.product.ci_contract_fixture_packets import write_capability_prerequisite_packets

    runs_dir = ROOT / "runs"
    write_capability_prerequisite_packets(runs_dir)
    builders = [
        ("tools/build_product_capability_surface_contract.py",),
        ("tools/build_product_architecture_contract.py",),
        ("tools/build_product_service_boundary_contract.py",),
        ("tools/build_product_api_contract.py",),
        ("tools/build_product_operational_quality_contract.py",),
        ("tools/build_product_security_deployment_contract.py",),
        ("tools/build_product_job_orchestration_contract.py",),
        ("tools/build_product_production_ai_checkpoint_readiness.py",),
        ("tools/build_product_release_operations_dossier.py",),
        ("deploy/product_rollout.py", "--out-json", "runs/product_rollout_plan_current.json"),
        (
            "tools/smoke_alert_delivery.py",
            "--local-receiver-smoke",
            "--out-json",
            "runs/alert_delivery_smoke_current.json",
        ),
        ("tools/build_api_runner_profile_promotion_readiness.py",),
        (
            "tools/product/build_api_runner_profile_enablement_work_order.py",
            "--profiles-dir",
            "config/api_validated_runner_profiles",
            "--evidence-dir",
            evidence_dir,
            "--write-evidence-templates",
        ),
        ("tools/build_product_rollout_execution_readiness.py",),
        ("tools/build_product_rollout_execution_smoke_receipt.py",),
        ("tools/build_viewer_asset_base_url_decision.py", "--out-json", "runs/viewer_asset_base_url_decision_current.json"),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_release_decision_gate.py",),
        ("tools/build_goal_release_burndown_work_order.py",),
        ("tools/build_goal_operator_action_board.py",),
        ("tools/build_goal_operator_intake_kit.py",),
        ("tools/build_goal_bottleneck_briefing.py",),
        ("tools/build_goal_api_surface_contract.py",),
        ("tools/product/build_api_runner_profile_promotion_operator_receipt.py",),
        ("tools/product/build_self_hosted_license_distribution_audit.py",),
        ("tools/build_third_party_license_review_gate.py",),
        ("tools/build_gpcr_conditional_prior_promotion_gate.py",),
        ("tools/product/build_transporter_claim_promotion_boundary.py",),
        ("tools/wetlab/build_wetlab_openmm_claim_promotion_boundary.py",),
        ("tools/build_science_claim_promotion_gap_closure.py",),
        ("tools/build_deploy_ops_legal_gap_closure.py",),
        ("tools/build_storage_cleanup_gap_closure.py",),
        ("tools/build_tools_package_other_review_classification_plan.py",),
        ("tools/build_tools_package_batch3_review_plan.py",),
        ("tools/build_tools_refactor_gap_closure.py",),
        ("tools/build_product_infrastructure_gap_closure.py",),
        ("tools/build_public_benchmark_residual_assist_replays.py",),
        ("tools/build_public_benchmark_residual_assist_comparisons.py",),
        ("tools/build_public_benchmark_residual_assist_comparison_gate.py",),
        ("tools/build_architecture_validation_public_benchmark_subset_manifests.py",),
        ("tools/build_architecture_validation_speedpack_ab_retrospective.py",),
    ]
    for command in builders:
        _run(*command)
    from tools.product.ci_contract_fixture_packets import (
        write_cameo_api_surface_fixture_packets,
        write_commercial_readiness_operator_surface_fixture_packets,
        write_product_scope_breadth_priority_fixture_packets,
        write_production_ai_checkpoint_fixture_packets,
        write_deploy_ops_legal_closure_packets,
        write_restricted_accuracy_parity_scorecard,
        write_restricted_engine_refinement_claim_evidence_priority_packet,
        write_restricted_goal_bottleneck_briefing,
        write_restricted_goal_release_decision_gate,
        write_restricted_commercial_readiness_handoff_bundle,
        write_restricted_production_ai_checkpoint_readiness_contract,
        write_restricted_product_goal_completion_audit,
        write_restricted_self_hosted_commercial_packets,
    )
    from tools.product.write_full_gap_closure_fixture_packets import write_full_gap_closure_fixture_packets

    write_full_gap_closure_fixture_packets(runs_dir)
    write_restricted_self_hosted_commercial_packets(runs_dir)
    write_cameo_api_surface_fixture_packets(runs_dir)
    post_builders = [
        ("tools/build_product_scope_breadth_evidence_intake_readiness.py",),
        ("tools/build_product_scope_breadth_evidence_acquisition_queue.py",),
        ("tools/build_product_scope_breadth_evidence_priority_packet.py",),
        ("tools/build_product_scope_breadth_contract.py",),
        ("tools/build_general_protein_ligand_claim_blocker_packet.py",),
        ("tools/build_product_scope_breadth_closure_checklist.py",),
        ("tools/product/build_self_hosted_license_distribution_audit.py",),
        ("tools/build_third_party_license_review_gate.py",),
        ("tools/build_product_rollout_execution_smoke_receipt.py",),
        ("tools/build_deploy_ops_legal_gap_closure.py",),
        ("tools/build_commercial_gap_closure_status.py",),
        ("tools/build_product_production_ai_checkpoint_readiness.py",),
        ("tools/build_product_ai_architecture_gap_closure.py",),
        ("tools/build_product_ai_architecture_execution_backlog.py",),
        ("tools/build_data_science_expansion_gap_closure.py",),
        ("tools/build_master_gap_closure_rollup.py",),
        ("tools/build_accuracy_parity_scorecard.py",),
        ("tools/cameo/build_cameo_local_format_smoke_inputs.py",),
        ("tools/build_cameo_api_dependency_readiness.py",),
        ("tools/build_cameo_receiver_smoke_contract.py",),
        (
            "tools/build_cameo_format_validation_packet.py",
            "--models-csv",
            "runs/cameo_local_format_smoke_inputs_current/models.csv",
        ),
        (
            "tools/build_cameo_model1_selection_packet.py",
            "--candidates-csv",
            "runs/cameo_local_format_smoke_inputs_current/candidates.csv",
        ),
        ("tools/build_cameo_dry_run_handoff_packet.py",),
        ("tools/build_cameo_validation_readiness_gate.py",),
        ("tools/build_cameo_official_results_intake_gate.py",),
        ("tools/build_competition_benchmark_rollup.py",),
        ("tools/build_architecture_validation_package_report.py",),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_release_decision_gate.py",),
        ("tools/build_goal_release_burndown_work_order.py",),
        ("tools/build_goal_bottleneck_briefing.py",),
        ("tools/build_goal_operator_action_board.py",),
        ("tools/build_goal_operator_intake_kit.py",),
        ("tools/build_product_release_operations_dossier.py",),
        ("tools/build_product_goal_completion_audit.py",),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_release_decision_gate.py",),
        ("tools/build_goal_release_burndown_work_order.py",),
        ("tools/build_goal_operator_action_board.py",),
        ("tools/build_goal_operator_intake_kit.py",),
        ("tools/build_goal_bottleneck_briefing.py",),
        ("tools/build_goal_api_surface_contract.py",),
    ]
    for command in post_builders:
        _run(*command)
    write_restricted_self_hosted_commercial_packets(runs_dir)
    write_restricted_accuracy_parity_scorecard(runs_dir)
    write_cameo_api_surface_fixture_packets(runs_dir)
    write_product_scope_breadth_priority_fixture_packets(runs_dir)
    write_production_ai_checkpoint_fixture_packets(runs_dir)
    _run("tools/build_product_production_ai_checkpoint_readiness.py")
    write_restricted_production_ai_checkpoint_readiness_contract(runs_dir)
    _run("tools/build_product_commercial_readiness_handoff_bundle.py")
    write_restricted_commercial_readiness_handoff_bundle(runs_dir)
    final_builders = [
        ("tools/product/build_product_production_ai_promotion_workbench.py",),
        ("tools/product/build_production_ai_registry_promotion_operator_receipt.py",),
        ("tools/product/build_production_ai_registry_promotion_priority_packet.py",),
        ("tools/product/build_product_pose_sampling_readiness.py",),
        ("scripts/verify_quality_gate.py", "--quiet", "--out-json", "runs/product_quality_gate_verification_current.json"),
        ("tools/product/build_engine_refinement_tier_readiness.py",),
        ("tools/product/build_engine_refinement_claim_evidence_receipt.py",),
        ("tools/product/build_engine_refinement_claim_evidence_priority_packet.py",),
        ("tools/product/build_engine_refinement_tier_readiness.py",),
        ("tools/product/build_product_scope_breadth_evidence_receipt.py",),
        ("tools/build_product_goal_completion_audit.py",),
        ("tools/product/build_product_full_commercial_blocker_evidence_matrix.py",),
        ("tools/build_product_goal_completion_audit.py",),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_release_decision_gate.py",),
        ("tools/build_goal_release_burndown_work_order.py",),
        ("tools/build_goal_operator_action_board.py",),
        ("tools/build_goal_operator_intake_kit.py",),
        ("tools/build_goal_bottleneck_briefing.py",),
        ("tools/build_goal_api_surface_contract.py",),
    ]
    for command in final_builders:
        _run(*command)
    write_restricted_engine_refinement_claim_evidence_priority_packet(runs_dir)
    write_deploy_ops_legal_closure_packets(runs_dir)
    _run("tools/product/build_self_hosted_license_distribution_audit.py")
    write_restricted_product_goal_completion_audit(runs_dir)
    _run("tools/product/build_product_full_commercial_blocker_evidence_matrix.py")
    write_restricted_goal_bottleneck_briefing(runs_dir)
    write_restricted_goal_release_decision_gate(runs_dir)
    _run("tools/product/build_product_full_commercial_blocker_evidence_matrix.py")
    write_commercial_readiness_operator_surface_fixture_packets(runs_dir)
    commercial_operator_builders = [
        ("tools/build_production_ai_registry_promotion_operator_field_worksheet.py",),
        ("tools/build_production_ai_registry_promotion_operator_staging_apply.py",),
        ("tools/build_product_scope_breadth_evidence_operator_field_worksheet.py",),
        ("tools/build_product_scope_breadth_evidence_operator_staging_apply.py",),
        ("tools/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py",),
        ("tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py",),
        (
            "tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py",
            "--mode",
            "preview",
            "--staging-csv",
            "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv",
        ),
        ("tools/build_product_commercial_readiness_operator_packet.py",),
    ]
    for command in commercial_operator_builders:
        _run(*command)
    write_commercial_readiness_operator_surface_fixture_packets(runs_dir)
    commercial_operator_followup_builders = [
        ("tools/build_product_commercial_readiness_operator_packet_freshness.py",),
        ("tools/build_product_commercial_readiness_execution_ladder.py",),
        ("tools/build_product_commercial_readiness_handoff_bundle.py",),
    ]
    for command in commercial_operator_followup_builders:
        _run(*command)
    write_restricted_commercial_readiness_handoff_bundle(runs_dir)
    write_restricted_product_goal_completion_audit(runs_dir)
    _run("tools/product/build_product_full_commercial_blocker_evidence_matrix.py")
    write_restricted_goal_bottleneck_briefing(runs_dir)
    write_restricted_goal_release_decision_gate(runs_dir)
    _run("tools/product/build_product_launch_r4_preflight.py")
    _run("tools/build_goal_api_surface_contract.py")


def main(argv: list[str] | None = None) -> int:
    materialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
