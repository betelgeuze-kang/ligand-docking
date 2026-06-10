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
        ("tools/build_viewer_asset_base_url_decision.py", "--out-json", "runs/viewer_asset_base_url_decision_current.json"),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_release_decision_gate.py",),
        ("tools/build_goal_release_burndown_work_order.py",),
        ("tools/build_goal_bottleneck_briefing.py",),
        ("tools/build_goal_operator_action_board.py",),
        ("tools/build_goal_operator_intake_kit.py",),
        ("tools/build_goal_api_surface_contract.py",),
        ("tools/product/build_self_hosted_license_distribution_audit.py",),
        ("tools/build_third_party_license_review_gate.py",),
        ("tools/build_gpcr_conditional_prior_promotion_gate.py",),
        ("tools/build_transporter_claim_promotion_boundary.py",),
        ("tools/build_wetlab_openmm_claim_promotion_boundary.py",),
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
    ]
    for command in builders:
        _run(*command)
    from tools.product.write_full_gap_closure_fixture_packets import write_full_gap_closure_fixture_packets

    write_full_gap_closure_fixture_packets(runs_dir)
    post_builders = [
        ("tools/product/build_self_hosted_license_distribution_audit.py",),
        ("tools/build_third_party_license_review_gate.py",),
        ("tools/build_deploy_ops_legal_gap_closure.py",),
        ("tools/build_commercial_gap_closure_status.py",),
        ("tools/build_product_ai_architecture_gap_closure.py",),
        ("tools/build_product_ai_architecture_execution_backlog.py",),
        ("tools/build_data_science_expansion_gap_closure.py",),
        ("tools/build_master_gap_closure_rollup.py",),
        ("tools/build_goal_readiness_rollup.py",),
        ("tools/build_goal_operator_action_board.py",),
    ]
    for command in post_builders:
        _run(*command)


def main(argv: list[str] | None = None) -> int:
    materialize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
