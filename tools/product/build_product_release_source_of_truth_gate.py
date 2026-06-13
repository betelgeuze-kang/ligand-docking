#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_OUT_CSV = "runs/product_release_source_of_truth_gate_current.csv"
DEFAULT_OUT_MD = "runs/product_release_source_of_truth_gate_current.md"

CLAIM_BOUNDARY = (
    "Product release source-of-truth gate only; it checks local current artifact freshness, source/dependency "
    "ordering, and README metric drift. It does not run docking, execute GPU jobs, assemble bundles, submit "
    "external validation, upload, delete, email, commit, push, or mutate external state."
)

RELEASE_REFRESH_COMMANDS = [
    "python3 tools/build_accuracy_parity_scorecard.py",
    "python3 tools/build_residual_shadow_ab.py",
    "python3 tools/build_residual_model_registry.py",
    "python3 tools/build_residual_force_derivation_validation.py",
    "python3 tools/build_product_production_ai_checkpoint_readiness.py",
    "python3 tools/build_product_production_ai_promotion_workbench.py",
    "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
    "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
    "python3 tools/build_product_scope_breadth_contract.py",
    "python3 tools/build_product_scope_breadth_closure_checklist.py",
    "python3 tools/build_product_scope_breadth_evidence_receipt.py",
    "python3 tools/build_product_operational_quality_contract.py",
    "python3 tools/build_api_runner_profile_promotion_readiness.py",
    "python3 tools/build_api_runner_profile_promotion_operator_receipt.py",
    "python3 tools/gpcr_replay/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 180",
    "python3 tools/build_api_docking_dispatch_e2e_evidence.py",
    "python3 tools/build_product_job_orchestration_contract.py",
    "python3 tools/product/build_restricted_unattended_execution_readiness.py",
    "python3 tools/build_product_security_deployment_contract.py",
    "python3 tools/build_product_execution_work_order.py",
    "python3 tools/build_product_execution_preflight.py",
    "python3 tools/build_local_delivery_environment_manifest.py --accelerator-env TORCH_BLAS_PREFER_HIPBLASLT=0 --no-probe-accelerator-commands",
    "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py",
    "python3 tools/build_product_bundle_contract.py",
    "python3 tools/build_product_delivery_evidence_contract.py",
    "python3 tools/build_product_pilot_packet_contract.py",
    "python3 tools/build_product_api_contract.py",
    "python3 tools/build_product_service_boundary_contract.py",
    "python3 tools/build_product_capability_surface_contract.py",
    "python3 tools/build_product_commercial_independence_gate.py",
    "python3 tools/product/build_self_hosted_license_distribution_audit.py",
    "python3 tools/build_third_party_license_review_gate.py",
    "python3 deploy/product_rollout.py --out-json runs/product_rollout_plan_current.json",
    "python3 tools/smoke_alert_delivery.py --local-receiver-smoke --allow-in-process-fallback --out-json runs/alert_delivery_smoke_current.json",
    "python3 tools/build_product_pose_sampling_readiness.py",
    "python3 tools/build_product_trajectory_sla_contract.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_ai_decision_graph_contract.py",
    "python3 tools/build_product_ai_report_explanation_packet.py",
    "python3 tools/build_product_ai_report_ux_contract.py",
    "python3 tools/build_product_ai_decision_graph_contract.py",
    "python3 tools/build_product_rollout_execution_readiness.py",
    "python3 tools/build_api_customer_flow_release_evidence.py",
    "python3 tools/product/build_refine_tier_public_benchmark_readiness.py",
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py",
    "python3 tools/product/build_engine_refinement_tier_readiness.py",
    "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py",
    "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
    "python3 tools/product/build_product_launch_r4_preflight.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_release_operations_dossier.py",
    "python3 tools/build_product_architecture_contract.py",
    "python3 tools/build_cameo_official_result_fetch_preflight.py",
    "python3 tools/build_cameo_public_registration_approval_gate.py",
    "python3 tools/build_cameo_outbound_email_send_preflight.py",
    "python3 tools/build_cameo_validation_operations_dossier.py",
    "python3 tools/build_cameo_architecture_validation_contract.py",
    "python3 tools/build_goal_readiness_rollup.py",
    "python3 tools/build_product_goal_completion_audit.py",
    "python3 tools/build_goal_operator_action_board.py",
    "python3 tools/build_goal_operator_intake_kit.py",
    "python3 tools/build_goal_api_surface_contract.py",
    "python3 tools/build_goal_bottleneck_briefing.py",
    "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_commercial_readiness_operator_packet.py",
    "python3 tools/build_product_commercial_readiness_operator_packet_freshness.py",
    "python3 tools/build_product_commercial_readiness_execution_ladder.py",
    "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
    "python3 tools/build_product_rollout_execution_smoke_receipt.py",
    "python3 tools/build_deploy_ops_legal_gap_closure.py",
    "python3 tools/build_science_claim_promotion_gap_closure.py",
    "python3 tools/build_master_gap_closure_rollup.py",
    "python3 tools/build_product_ledger_privacy_scan.py",
    "python3 tools/build_product_release_source_of_truth_gate.py",
    "python3 tools/build_goal_release_decision_gate.py",
]

DEFAULT_ARTIFACT_SPECS: list[dict[str, Any]] = [
    {
        "artifact_id": "accuracy_parity_scorecard",
        "artifact_path": "runs/accuracy_parity_scorecard_current.json",
        "builder_command": "python3 tools/build_accuracy_parity_scorecard.py",
        "depends_on": [],
    },
    {
        "artifact_id": "residual_model_registry",
        "artifact_path": "runs/residual_model_registry_current.json",
        "builder_command": "python3 tools/build_residual_model_registry.py",
        "depends_on": [
            "tools/product/build_residual_shadow_ab.py",
            "tools/accounting/build_residual_model_registry.py",
            "runs/residual_shadow_ab_current.json",
            "runs/residual_assist_promotion_gate_current.json",
            "runs/gpcr_residual_proof_breadth_gate_current.json",
            "runs/public_benchmark_residual_assist_comparison_gate_current.json",
            "runs/residual_production_checkpoint_preflight_current.json",
            "runs/residual_production_checkpoint_sidecar_current.json",
        ],
    },
    {
        "artifact_id": "product_production_ai_checkpoint_readiness",
        "artifact_path": "runs/product_production_ai_checkpoint_readiness_current.json",
        "builder_command": "python3 tools/build_product_production_ai_checkpoint_readiness.py",
        "depends_on": [
            "runs/residual_model_registry_current.json",
            "runs/residual_force_derivation_validation_current.json",
        ],
    },
    {
        "artifact_id": "product_production_ai_promotion_workbench",
        "artifact_path": "runs/product_production_ai_promotion_workbench_current.json",
        "builder_command": "python3 tools/build_product_production_ai_promotion_workbench.py",
        "depends_on": [
            "tools/product/build_product_production_ai_promotion_workbench.py",
            "runs/product_production_ai_checkpoint_readiness_current.json",
        ],
    },
    {
        "artifact_id": "production_ai_registry_promotion_operator_receipt",
        "artifact_path": "runs/production_ai_registry_promotion_operator_receipt_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
        "depends_on": [
            "tools/product/build_production_ai_registry_promotion_operator_receipt.py",
            "tools/accounting/build_production_ai_registry_promotion_operator_receipt.py",
            "tools/build_production_ai_registry_promotion_operator_receipt.py",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
        ],
    },
    {
        "artifact_id": "production_ai_registry_promotion_priority_packet",
        "artifact_path": "runs/production_ai_registry_promotion_priority_packet_current.json",
        "builder_command": "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
        "depends_on": [
            "tools/product/build_production_ai_registry_promotion_priority_packet.py",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
            "runs/product_production_ai_promotion_workbench_current.json",
        ],
    },
    {
        "artifact_id": "product_scope_breadth_contract",
        "artifact_path": "runs/product_scope_breadth_contract_current.json",
        "builder_command": "python3 tools/build_product_scope_breadth_contract.py",
        "depends_on": [],
    },
    {
        "artifact_id": "product_scope_breadth_closure_checklist",
        "artifact_path": "runs/product_scope_breadth_closure_checklist_current.json",
        "builder_command": "python3 tools/build_product_scope_breadth_closure_checklist.py",
        "depends_on": [
            "tools/accounting/build_product_scope_breadth_closure_checklist.py",
            "tools/build_product_scope_breadth_closure_checklist.py",
            "runs/transporter_slot_assignment_candidate_workbook_current.json",
            "runs/transporter_manual_review_intake_template_current.json",
            "runs/pxr_authoritative_reconciliation_packet_current.json",
            "runs/pxr_exact_evidence_review_intake_template_current.json",
            "runs/general_protein_ligand_claim_blocker_packet_current.json",
        ],
    },
    {
        "artifact_id": "product_scope_breadth_evidence_receipt",
        "artifact_path": "runs/product_scope_breadth_evidence_receipt_current.json",
        "builder_command": "python3 tools/build_product_scope_breadth_evidence_receipt.py",
        "depends_on": [
            "tools/product/build_product_scope_breadth_evidence_receipt.py",
            "tools/build_product_scope_breadth_evidence_receipt.py",
            "config/product_scope_breadth_evidence_receipt_current.csv",
            "runs/product_scope_breadth_closure_checklist_current.json",
        ],
    },
    {
        "artifact_id": "product_operational_quality_contract",
        "artifact_path": "runs/product_operational_quality_contract_current.json",
        "builder_command": "python3 tools/build_product_operational_quality_contract.py",
        "depends_on": [
            "betelgeuze_product/operational_quality.py",
            "betelgeuze_product/docking_request.py",
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_promotion_workbench_current.json",
        ],
    },
    {
        "artifact_id": "api_runner_profile_promotion_readiness",
        "artifact_path": "runs/api_runner_profile_promotion_readiness_current.json",
        "builder_command": "python3 tools/build_api_runner_profile_promotion_readiness.py",
        "depends_on": [
            "tools/product/build_api_runner_profile_promotion_readiness.py",
            "config/api_validated_runner_profiles",
        ],
    },
    {
        "artifact_id": "api_runner_profile_promotion_operator_receipt",
        "artifact_path": "runs/api_runner_profile_promotion_operator_receipt_current.json",
        "builder_command": "python3 tools/build_api_runner_profile_promotion_operator_receipt.py",
        "depends_on": [
            "tools/product/build_api_runner_profile_promotion_operator_receipt.py",
            "runs/api_runner_profile_promotion_readiness_current.json",
            "runs/api_runner_profile_promotion_operator_template_current.csv",
        ],
    },
    {
        "artifact_id": "tier_alpha_adrb2_dispatch_smoke",
        "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
            "builder_command": "python3 tools/gpcr_replay/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 180",
            "depends_on": [
                "tools/gpcr_replay/run_tier_alpha_adrb2_dispatch_smoke.py",
            "api/worker.py",
            "api/docking_dispatch.py",
            "api/validated_runner.py",
            "api/result_manifest.py",
            "runs/api_runner_profile_promotion_readiness_current.json",
        ],
    },
    {
        "artifact_id": "api_docking_dispatch_e2e_evidence",
        "artifact_path": "runs/api_docking_dispatch_e2e_evidence_current.json",
        "builder_command": "python3 tools/build_api_docking_dispatch_e2e_evidence.py",
        "depends_on": [
            "tools/product/build_api_docking_dispatch_e2e_evidence.py",
            "runs/api_runner_profile_promotion_readiness_current.json",
            "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
        ],
    },
    {
        "artifact_id": "product_job_orchestration_contract",
        "artifact_path": "runs/product_job_orchestration_contract_current.json",
        "builder_command": "python3 tools/build_product_job_orchestration_contract.py",
        "depends_on": [
            "tools/product/build_product_job_orchestration_contract.py",
            "tools/accounting/build_product_job_orchestration_contract.py",
            "tools/build_product_job_orchestration_contract.py",
            "betelgeuze_product/docking_request.py",
            "betelgeuze_product/job_orchestration.py",
        ],
    },
    {
        "artifact_id": "restricted_unattended_execution_readiness",
        "artifact_path": "runs/restricted_unattended_execution_readiness_current.json",
        "builder_command": "python3 tools/product/build_restricted_unattended_execution_readiness.py",
        "depends_on": [
            "tools/product/build_restricted_unattended_execution_readiness.py",
            "runs/api_docking_dispatch_e2e_evidence_current.json",
            "runs/api_runner_profile_promotion_readiness_current.json",
            "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
        ],
    },
    {
        "artifact_id": "product_security_deployment_contract",
        "artifact_path": "runs/product_security_deployment_contract_current.json",
        "builder_command": "python3 tools/build_product_security_deployment_contract.py",
        "depends_on": [
            "tools/product/build_product_security_deployment_contract.py",
            "api/config.py",
            "api/security.py",
            "api/main.py",
            "Dockerfile.product",
            "docs/product_security_deployment_policy.md",
        ],
    },
    {
        "artifact_id": "product_execution_work_order",
        "artifact_path": "runs/product_execution_work_order_current.json",
        "builder_command": "python3 tools/build_product_execution_work_order.py",
        "depends_on": [
            "tools/accounting/build_product_execution_work_order.py",
            "betelgeuze_product/work_order.py",
            "betelgeuze_product/htvs_command.py",
            "runs/product_readiness_gate_current.json",
            "config/ligand_htvs_blind_gpcr_adrb2_chembl20_product_gate_repair_v1.json",
        ],
    },
    {
        "artifact_id": "product_execution_preflight",
        "artifact_path": "runs/product_execution_preflight_current.json",
        "builder_command": "python3 tools/build_product_execution_preflight.py",
        "depends_on": [
            "tools/accounting/build_product_execution_preflight.py",
            "betelgeuze_product/execution_preflight.py",
            "runs/product_execution_work_order_current.json",
        ],
    },
    {
        "artifact_id": "local_delivery_environment_manifest",
        "artifact_path": "runs/local_delivery_environment_manifest_current.json",
        "builder_command": "python3 tools/build_local_delivery_environment_manifest.py --accelerator-env TORCH_BLAS_PREFER_HIPBLASLT=0 --no-probe-accelerator-commands",
        "depends_on": [
            "tools/accounting/build_local_delivery_environment_manifest.py",
            "tools/build_local_delivery_environment_manifest.py",
            "requirements.txt",
            "requirements-dev.txt",
            "runs/local_delivery_requirements_lock_current.json",
            "runs/local_delivery_requirements_lock_current.md",
            "runs/local_delivery_requirements_lock_current.txt",
        ],
    },
    {
        "artifact_id": "wetlab_selected_allatom_gate_burndown",
        "artifact_path": "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
        "builder_command": "python3 tools/build_wetlab_selected_allatom_gate_burndown_packet.py",
        "depends_on": [
            "tools/accounting/build_wetlab_selected_allatom_gate_burndown_packet.py",
            "tools/build_wetlab_selected_allatom_gate_burndown_packet.py",
            "runs/wetlab_master_handoff_dashboard_current.json",
            "runs/wetlab_final_campaign_summary_current.json",
            "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
        ],
    },
    {
        "artifact_id": "product_bundle_contract",
        "artifact_path": "runs/product_bundle_contract_current.json",
        "builder_command": "python3 tools/build_product_bundle_contract.py",
        "depends_on": [
            "tools/accounting/build_product_bundle_contract.py",
            "tools/build_product_bundle_contract.py",
            "betelgeuze_product/bundle_contract.py",
            "runs/product_execution_work_order_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json",
        ],
    },
    {
        "artifact_id": "product_delivery_evidence_contract",
        "artifact_path": "runs/product_delivery_evidence_contract_current.json",
        "builder_command": "python3 tools/build_product_delivery_evidence_contract.py",
        "depends_on": [
            "tools/accounting/build_product_delivery_evidence_contract.py",
            "tools/build_product_delivery_evidence_contract.py",
            "betelgeuze_product/delivery_evidence.py",
            "runs/product_readiness_gate_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/local_delivery_verdict_gate_current.json",
            "runs/local_delivery_preflight_current.json",
            "runs/local_delivery_environment_manifest_current.json",
            "runs/local_delivery_requirements_lock_current.json",
            "runs/local_delivery_engine_provenance_current.json",
            "runs/local_engine_commercialization_queue_current.json",
            "runs/nightly_gate_burndown_packet_current.json",
            "runs/wetlab_selected_allatom_gate_burndown_packet_current.json",
        ],
    },
    {
        "artifact_id": "product_pilot_packet_contract",
        "artifact_path": "runs/product_pilot_packet_contract_current.json",
        "builder_command": "python3 tools/build_product_pilot_packet_contract.py",
        "depends_on": [
            "tools/accounting/build_product_pilot_packet_contract.py",
            "tools/build_product_pilot_packet_contract.py",
            "betelgeuze_product/pilot_packet.py",
            "runs/product_readiness_gate_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/product_delivery_evidence_contract_current.json",
            "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json",
        ],
    },
    {
        "artifact_id": "product_api_contract",
        "artifact_path": "runs/product_api_contract_current.json",
        "builder_command": "python3 tools/build_product_api_contract.py",
        "depends_on": [
            "tools/accounting/build_product_api_contract.py",
            "tools/build_product_api_contract.py",
            "betelgeuze_product/api_contract.py",
            "api/product.py",
        ],
    },
    {
        "artifact_id": "product_service_boundary_contract",
        "artifact_path": "runs/product_service_boundary_contract_current.json",
        "builder_command": "python3 tools/build_product_service_boundary_contract.py",
        "depends_on": [
            "tools/accounting/build_product_service_boundary_contract.py",
            "tools/build_product_service_boundary_contract.py",
            "betelgeuze_product/service_boundary.py",
            "betelgeuze_product/cli.py",
            "api/product.py",
            "pyproject.toml",
        ],
    },
    {
        "artifact_id": "product_capability_surface_contract",
        "artifact_path": "runs/product_capability_surface_contract_current.json",
        "builder_command": "python3 tools/build_product_capability_surface_contract.py",
        "depends_on": [
            "runs/restricted_unattended_execution_readiness_current.json",
            "runs/product_security_deployment_contract_current.json",
        ],
    },
    {
        "artifact_id": "product_commercial_independence_gate",
        "artifact_path": "runs/product_commercial_independence_gate_current.json",
        "builder_command": "python3 tools/build_product_commercial_independence_gate.py",
        "depends_on": [
            "tools/accounting/build_product_commercial_independence_gate.py",
            "betelgeuze_product/commercial_independence.py",
            "LICENSE",
            "requirements.txt",
            "requirements-api.txt",
            "requirements-deploy.txt",
            "requirements-optional.txt",
            "requirements-train.txt",
            "pyproject.toml",
            "Dockerfile.product",
            "runs/local_delivery_environment_manifest_current.json",
            "runs/local_delivery_requirements_lock_current.json",
            "runs/local_delivery_requirements_lock_current.md",
            "runs/local_delivery_requirements_lock_current.txt",
            "runs/product_api_contract_current.json",
            "runs/product_service_boundary_contract_current.json",
            "runs/product_capability_surface_contract_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/product_delivery_evidence_contract_current.json",
            "runs/product_pilot_packet_contract_current.json",
            "runs/product_public_benchmark_contract_current.json",
            "runs/product_public_benchmark_work_order_current.json",
        ],
    },
    {
        "artifact_id": "self_hosted_license_distribution_audit",
        "artifact_path": "runs/self_hosted_license_distribution_audit_current.json",
        "builder_command": "python3 tools/product/build_self_hosted_license_distribution_audit.py",
        "depends_on": [
            "tools/product/build_self_hosted_license_distribution_audit.py",
            "LICENSE",
            "runs/product_license_decision_gate_current.json",
            "runs/product_license_file_creation_work_order_current.json",
            "runs/product_commercial_independence_gate_current.json",
            "viewer/vendor/manifest.json",
            "viewer/vendor/THIRD_PARTY_NOTICES.md",
        ],
    },
    {
        "artifact_id": "third_party_license_review_gate",
        "artifact_path": "runs/third_party_license_review_gate_current.json",
        "builder_command": "python3 tools/build_third_party_license_review_gate.py",
        "depends_on": [
            "tools/product/build_third_party_license_review_gate.py",
            "tools/accounting/build_third_party_license_review_gate.py",
            "tools/build_third_party_license_review_gate.py",
            "runs/self_hosted_license_distribution_audit_current.json",
            "runs/third_party_license_review_operator_intake.csv",
        ],
    },
    {
        "artifact_id": "product_rollout_plan",
        "artifact_path": "runs/product_rollout_plan_current.json",
        "builder_command": "python3 deploy/product_rollout.py --out-json runs/product_rollout_plan_current.json",
        "depends_on": ["deploy/product_rollout.py"],
    },
    {
        "artifact_id": "alert_delivery_smoke",
        "artifact_path": "runs/alert_delivery_smoke_current.json",
        "builder_command": "python3 tools/smoke_alert_delivery.py --local-receiver-smoke --allow-in-process-fallback --out-json runs/alert_delivery_smoke_current.json",
        "depends_on": ["tools/smoke_alert_delivery.py"],
    },
    {
        "artifact_id": "product_release_bundle",
        "artifact_path": "runs/product_release_bundle_current.json",
        "builder_command": "python3 deploy/product_release_bundle.py",
        "depends_on": [
            "deploy/product_release_bundle.py",
            "runs/product_security_deployment_contract_current.json",
            "runs/product_rollout_plan_current.json",
            "runs/alert_delivery_smoke_current.json",
            "runs/self_hosted_license_distribution_audit_current.json",
            "runs/third_party_license_review_gate_current.json",
            "runs/product_launch_r4_preflight_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "runs/api_runner_profile_promotion_operator_receipt_current.json",
            "runs/product_pose_sampling_readiness_current.json",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/product_full_commercial_blocker_evidence_matrix_current.json",
            "runs/product_trajectory_sla_contract_current.json",
        ],
    },
    {
        "artifact_id": "product_pose_sampling_readiness",
        "artifact_path": "runs/product_pose_sampling_readiness_current.json",
        "builder_command": "python3 tools/build_product_pose_sampling_readiness.py",
        "depends_on": [
            "tools/product/build_product_pose_sampling_readiness.py",
            "tools/accounting/build_product_pose_sampling_readiness.py",
            "tools/build_product_pose_sampling_readiness.py",
            "core/pose_generation.py",
            "core/pocket_detection.py",
        ],
    },
    {
        "artifact_id": "product_trajectory_sla_contract",
        "artifact_path": "runs/product_trajectory_sla_contract_current.json",
        "builder_command": "python3 tools/build_product_trajectory_sla_contract.py",
        "depends_on": [
            "tools/product/build_product_trajectory_sla_contract.py",
            "tools/accounting/build_product_trajectory_sla_contract.py",
            "tools/build_product_trajectory_sla_contract.py",
            "runs/product_end_to_end_rocm_benchmark_current.json",
        ],
    },
    {
        "artifact_id": "product_ai_decision_graph_contract",
        "artifact_path": "runs/product_ai_decision_graph_contract_current.json",
        "builder_command": "python3 tools/build_product_ai_decision_graph_contract.py",
        "depends_on": [
            "tools/product/build_product_ai_decision_graph_contract.py",
            "runs/product_pose_sampling_readiness_current.json",
            "runs/product_structure_analysis_report_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/product_capability_surface_contract_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/residual_model_registry_current.json",
            "runs/product_ai_report_ux_contract_current.json",
        ],
    },
    {
        "artifact_id": "product_ai_report_explanation_packet",
        "artifact_path": "runs/product_ai_report_explanation_packet_current.json",
        "builder_command": "python3 tools/build_product_ai_report_explanation_packet.py",
        "depends_on": [
            "tools/product/build_product_ai_report_explanation_packet.py",
            "runs/product_structure_analysis_report_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/residual_model_registry_current.json",
            "runs/product_scope_breadth_closure_checklist_current.json",
        ],
    },
    {
        "artifact_id": "product_ai_report_ux_contract",
        "artifact_path": "runs/product_ai_report_ux_contract_current.json",
        "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
        "depends_on": [
            "tools/product/build_product_ai_report_ux_contract.py",
            "runs/product_ai_report_explanation_packet_current.json",
            "runs/product_structure_analysis_report_current.json",
            "runs/product_execution_preflight_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/residual_model_registry_current.json",
            "viewer/index.html",
            "viewer/app.js",
        ],
    },
    {
        "artifact_id": "product_rollout_execution_readiness",
        "artifact_path": "runs/product_rollout_execution_readiness_current.json",
        "builder_command": "python3 tools/build_product_rollout_execution_readiness.py",
        "depends_on": [
            "tools/product/build_product_rollout_execution_readiness.py",
            "deploy/product_release_bundle.py",
            "runs/product_rollout_plan_current.json",
            "runs/product_security_deployment_contract_current.json",
            "runs/alert_delivery_smoke_current.json",
        ],
    },
    {
        "artifact_id": "api_customer_flow_release_evidence",
        "artifact_path": "runs/api_customer_flow_release_evidence_current.json",
        "builder_command": "python3 tools/build_api_customer_flow_release_evidence.py",
        "depends_on": [
            "tools/product/build_api_customer_flow_release_evidence.py",
            "runs/api_docking_dispatch_e2e_evidence_current.json",
            "runs/restricted_unattended_execution_readiness_current.json",
            "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/product_delivery_evidence_contract_current.json",
            "runs/product_pilot_packet_contract_current.json",
        ],
    },
    {
        "artifact_id": "product_launch_r4_preflight",
        "artifact_path": "runs/product_launch_r4_preflight_current.json",
        "builder_command": "python3 tools/product/build_product_launch_r4_preflight.py",
        "depends_on": [
            "tools/product/build_product_launch_r4_preflight.py",
            "deploy/product_release_bundle.py",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/product_rollout_execution_readiness_current.json",
            "runs/product_commercial_independence_gate_current.json",
            "runs/product_license_decision_gate_current.json",
            "runs/third_party_license_review_gate_current.json",
            "runs/engine_refinement_tier_readiness_current.json",
        ],
    },
    {
        "artifact_id": "cameo_official_result_fetch_preflight",
        "artifact_path": "runs/cameo_official_result_fetch_preflight_current.json",
        "builder_command": "python3 tools/build_cameo_official_result_fetch_preflight.py",
        "depends_on": [
            "betelgeuze_cameo/official_result_fetch_preflight.py",
            "tools/cameo/build_cameo_official_result_fetch_preflight.py",
            "tools/accounting/build_cameo_official_result_fetch_preflight.py",
            "tools/build_cameo_official_result_fetch_preflight.py",
            "runs/cameo_official_result_fetch_operator_approval_template_current.csv",
        ],
    },
    {
        "artifact_id": "goal_readiness_rollup",
        "artifact_path": "runs/goal_readiness_rollup_current.json",
        "builder_command": "python3 tools/build_goal_readiness_rollup.py",
        "depends_on": [
            "runs/product_operational_quality_contract_current.json",
            "runs/product_capability_surface_contract_current.json",
            "runs/product_commercial_independence_gate_current.json",
            "runs/product_scope_breadth_contract_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/product_security_deployment_contract_current.json",
        ],
    },
    {
        "artifact_id": "engine_refinement_claim_promotion_action_board",
        "artifact_path": "runs/engine_refinement_claim_promotion_action_board_current.csv",
        "builder_command": "python3 tools/product/build_engine_refinement_tier_readiness.py",
        "depends_on": [
            "tools/product/build_engine_refinement_tier_readiness.py",
            "runs/engine_refinement_tier_readiness_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_readiness",
        "artifact_path": "runs/refine_tier_public_benchmark_readiness_current.json",
        "builder_command": "python3 tools/product/build_refine_tier_public_benchmark_readiness.py",
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_readiness.py",
            "config/refine_tier_public_benchmark_intake_current.csv",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_work_order_apply",
        "artifact_path": "runs/refine_tier_public_benchmark_work_order_apply_current.json",
        "builder_command": "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py",
        "depends_on": [
            "tools/product/apply_refine_tier_public_benchmark_work_order.py",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
        ],
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_receipt",
        "artifact_path": "runs/engine_refinement_claim_evidence_receipt_current.json",
        "builder_command": "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py",
        "depends_on": [
            "tools/product/build_engine_refinement_claim_evidence_receipt.py",
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "runs/engine_refinement_claim_promotion_action_board_current.csv",
        ],
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_priority_packet",
        "artifact_path": "runs/engine_refinement_claim_evidence_priority_packet_current.json",
        "builder_command": "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
        "depends_on": [
            "tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
            "runs/engine_refinement_claim_promotion_action_board_current.csv",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/refine_tier_public_benchmark_readiness_current.json",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_current.json",
        ],
    },
    {
        "artifact_id": "product_goal_completion_audit",
        "artifact_path": "runs/product_goal_completion_audit_current.json",
        "builder_command": "python3 tools/build_product_goal_completion_audit.py",
        "depends_on": [
            "runs/goal_readiness_rollup_current.json",
            "runs/engine_refinement_tier_readiness_current.json",
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
            "runs/product_scope_breadth_evidence_receipt_current.json",
        ],
    },
    {
        "artifact_id": "goal_operator_action_board",
        "artifact_path": "runs/goal_operator_action_board_current.json",
        "builder_command": "python3 tools/build_goal_operator_action_board.py",
        "depends_on": [
            "runs/goal_readiness_rollup_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/engine_refinement_claim_promotion_action_board_current.csv",
        ],
    },
    {
        "artifact_id": "goal_operator_intake_kit",
        "artifact_path": "runs/goal_operator_intake_kit_current/manifest.json",
        "builder_command": "python3 tools/build_goal_operator_intake_kit.py",
        "depends_on": [
            "tools/accounting/build_goal_operator_intake_kit.py",
            "tools/build_goal_operator_intake_kit.py",
            "runs/goal_operator_action_board_current.json",
            "runs/goal_release_burndown_work_order_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "config/product_scope_breadth_evidence_receipt_current.csv",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
        ],
    },
    {
        "artifact_id": "goal_api_surface_contract",
        "artifact_path": "runs/goal_api_surface_contract_current.json",
        "builder_command": "python3 tools/build_goal_api_surface_contract.py",
        "depends_on": [
            "tools/accounting/build_goal_api_surface_contract.py",
            "tools/build_goal_api_surface_contract.py",
            "api/goal.py",
            "api/main.py",
            "api/security.py",
        ],
    },
    {
        "artifact_id": "goal_bottleneck_briefing",
        "artifact_path": "runs/goal_bottleneck_briefing_current.json",
        "builder_command": "python3 tools/build_goal_bottleneck_briefing.py",
        "depends_on": [
            "tools/accounting/build_goal_bottleneck_briefing.py",
            "tools/build_goal_bottleneck_briefing.py",
            "runs/product_goal_completion_audit_current.json",
            "runs/goal_operator_action_board_current.json",
            "runs/goal_operator_intake_kit_current/manifest.json",
            "runs/goal_release_burndown_work_order_current.json",
            "runs/product_public_benchmark_work_order_current.json",
            "runs/dude_z_decoy_smoke_product_inputs_current.json",
            "runs/pdbbind_casf_pose_affinity_product_preflight_current.json",
            "runs/protein_protein_docking_benchmark_v5_product_preflight_current.json",
            "runs/casp_archive_structure_regression_product_preflight_current.json",
        ],
    },
    {
        "artifact_id": "product_full_commercial_blocker_evidence_matrix",
        "artifact_path": "runs/product_full_commercial_blocker_evidence_matrix_current.json",
        "builder_command": "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
        "depends_on": [
            "tools/product/build_product_full_commercial_blocker_evidence_matrix.py",
            "tools/build_product_full_commercial_blocker_evidence_matrix.py",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/goal_bottleneck_briefing_current.json",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_operator_packet",
        "artifact_path": "runs/product_commercial_readiness_operator_packet_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_operator_packet.py",
        "depends_on": [
            "runs/product_goal_completion_audit_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_handoff_bundle",
        "artifact_path": "runs/product_commercial_readiness_handoff_bundle_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
        "depends_on": [
            "runs/product_goal_completion_audit_current.json",
            "runs/product_commercial_readiness_operator_packet_current.json",
            "runs/product_commercial_readiness_operator_packet_freshness_current.json",
            "runs/product_commercial_readiness_execution_ladder_current.json",
            "runs/product_full_commercial_blocker_evidence_matrix_current.json",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_operator_packet_freshness",
        "artifact_path": "runs/product_commercial_readiness_operator_packet_freshness_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_operator_packet_freshness.py",
        "depends_on": [
            "runs/product_goal_completion_audit_current.json",
            "runs/product_commercial_readiness_operator_packet_current.json",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_execution_ladder",
        "artifact_path": "runs/product_commercial_readiness_execution_ladder_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_execution_ladder.py",
        "depends_on": [
            "runs/product_commercial_readiness_operator_packet_current.json",
            "runs/product_commercial_readiness_operator_packet_freshness_current.json",
        ],
    },
    {
        "artifact_id": "product_rollout_execution_smoke_receipt",
        "artifact_path": "runs/product_rollout_execution_smoke_receipt_current.json",
        "builder_command": "python3 tools/build_product_rollout_execution_smoke_receipt.py",
        "depends_on": [
            "tools/product/build_product_rollout_execution_smoke_receipt.py",
            "tools/build_product_rollout_execution_smoke_receipt.py",
            "runs/product_rollout_execution_readiness_current.json",
        ],
    },
    {
        "artifact_id": "deploy_ops_legal_gap_closure",
        "artifact_path": "runs/deploy_ops_legal_gap_closure_current.json",
        "builder_command": "python3 tools/build_deploy_ops_legal_gap_closure.py",
        "depends_on": [
            "tools/accounting/build_deploy_ops_legal_gap_closure.py",
            "tools/build_deploy_ops_legal_gap_closure.py",
            "runs/product_rollout_execution_readiness_current.json",
            "runs/product_rollout_execution_smoke_receipt_current.json",
            "runs/third_party_license_review_gate_current.json",
            "runs/product_license_decision_gate_current.json",
        ],
    },
    {
        "artifact_id": "science_claim_promotion_gap_closure",
        "artifact_path": "runs/science_claim_promotion_gap_closure_current.json",
        "builder_command": "python3 tools/build_science_claim_promotion_gap_closure.py",
        "depends_on": [
            "tools/accounting/build_science_claim_promotion_gap_closure.py",
            "tools/build_science_claim_promotion_gap_closure.py",
            "runs/gpcr_conditional_prior_promotion_gate_current.json",
            "runs/transporter_claim_promotion_boundary_current.json",
            "runs/ca2_packet_replacement_readiness_current.json",
            "runs/pxr_packet_replacement_readiness_current.json",
            "runs/wetlab_openmm_claim_promotion_boundary_current.json",
        ],
    },
    {
        "artifact_id": "master_gap_closure_rollup",
        "artifact_path": "runs/master_gap_closure_rollup_current.json",
        "builder_command": "python3 tools/build_master_gap_closure_rollup.py",
        "depends_on": [
            "tools/accounting/build_master_gap_closure_rollup.py",
            "tools/build_master_gap_closure_rollup.py",
            "runs/commercial_gap_closure_status_current.json",
            "runs/product_ai_architecture_gap_closure_current.json",
            "runs/data_science_expansion_gap_closure_current.json",
            "runs/product_infrastructure_gap_closure_current.json",
            "runs/science_claim_promotion_gap_closure_current.json",
            "runs/deploy_ops_legal_gap_closure_current.json",
            "runs/storage_cleanup_gap_closure_current.json",
            "runs/tools_refactor_gap_closure_current.json",
            "runs/api_runner_profile_promotion_readiness_current.json",
        ],
    },
    {
        "artifact_id": "product_ledger_privacy_scan",
        "artifact_path": "runs/product_ledger_privacy_scan_current.json",
        "builder_command": "python3 tools/build_product_ledger_privacy_scan.py",
        "depends_on": [
            "tools/product/build_product_ledger_privacy_scan.py",
            "betelgeuze_product/payload_privacy.py",
            "api/job_store.py",
            "api/validated_runner.py",
            "betelgeuze_product/docking_request.py",
            "betelgeuze_product/job_orchestration.py",
            "runs/product_operational_quality_contract_current.json",
            "runs/api_docking_dispatch_e2e_evidence_current.json",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/product_commercial_readiness_operator_packet_current.json",
            "runs/product_commercial_readiness_handoff_bundle_current.json",
            "runs/product_commercial_readiness_operator_packet_freshness_current.json",
            "runs/product_commercial_readiness_execution_ladder_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/goal_readiness_rollup_current.json",
            "runs/goal_operator_action_board_current.json",
            "runs/goal_operator_intake_kit_current/manifest.json",
            "runs/goal_release_burndown_work_order_current.json",
            "runs/goal_api_surface_contract_current.json",
            "runs/goal_bottleneck_briefing_current.json",
            "runs/product_full_commercial_blocker_evidence_matrix_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
        ],
    },
]

DEFAULT_STATUS_SPECS: list[dict[str, Any]] = [
    {
        "artifact_id": "product_bundle_contract_semantic_ready",
        "artifact_path": "runs/product_bundle_contract_current.json",
        "builder_command": "python3 tools/build_product_bundle_contract.py",
        "required_status": "product_bundle_contract_ready",
        "required_true_fields": [
            "bundle_validation_command_matches",
            "bundle_validation_present",
            "bundle_validation_passed",
            "bundle_assembled",
        ],
        "required_int_min_fields": {
            "artifact_count": 1,
        },
        "required_int_exact_fields": {
            "blocker_count": 0,
            "bundle_unknown_arg_count": 0,
        },
    },
    {
        "artifact_id": "product_delivery_evidence_contract_semantic_ready",
        "artifact_path": "runs/product_delivery_evidence_contract_current.json",
        "builder_command": "python3 tools/build_product_delivery_evidence_contract.py",
        "required_status": "product_delivery_evidence_contract_ready",
        "required_true_fields": [
            "delivery_ready_claim_allowed",
            "bundle_assembled",
            "bundle_validation_passed",
        ],
        "required_int_min_fields": {
            "evidence_check_count": 1,
            "evidence_pass_count": 1,
        },
        "required_int_exact_fields": {
            "blocker_count": 0,
        },
    },
    {
        "artifact_id": "product_pilot_packet_contract_semantic_ready",
        "artifact_path": "runs/product_pilot_packet_contract_current.json",
        "builder_command": "python3 tools/build_product_pilot_packet_contract.py",
        "required_status": "product_pilot_packet_ready",
        "required_true_fields": [
            "bundle_dir_exists",
            "bundle_assembled",
            "bundle_validation_present",
            "bundle_validation_passed",
            "delivery_ready_claim_allowed",
            "pilot_delivery_ready",
        ],
        "required_int_exact_fields": {
            "blocker_count": 0,
        },
    },
    {
        "artifact_id": "product_api_contract_semantic_ready",
        "artifact_path": "runs/product_api_contract_current.json",
        "builder_command": "python3 tools/build_product_api_contract.py",
        "required_status": "product_api_contract_ready",
        "required_true_fields": [
            "api_contract_ready",
        ],
        "required_int_min_fields": {
            "expected_route_count": 1,
        },
        "required_int_exact_fields": {
            "missing_route_count": 0,
            "status_response_missing_key_count": 0,
        },
    },
    {
        "artifact_id": "product_service_boundary_contract_semantic_ready",
        "artifact_path": "runs/product_service_boundary_contract_current.json",
        "builder_command": "python3 tools/build_product_service_boundary_contract.py",
        "required_status": "product_service_boundary_contract_ready",
        "required_true_fields": [
            "service_boundary_ready",
            "console_script_ready",
        ],
        "required_int_min_fields": {
            "api_route_count": 1,
            "cli_command_count": 1,
        },
        "required_int_exact_fields": {
            "missing_api_route_count": 0,
            "missing_cli_command_count": 0,
            "artifact_registry_mismatch_count": 0,
        },
    },
    {
        "artifact_id": "self_hosted_license_distribution_audit_semantic_ready",
        "artifact_path": "runs/self_hosted_license_distribution_audit_current.json",
        "builder_command": "python3 tools/product/build_self_hosted_license_distribution_audit.py",
        "required_status": "self_hosted_license_distribution_audit_recorded",
        "required_true_fields": [],
        "required_int_min_fields": {
            "operator_review_item_count": 0,
        },
        "required_int_exact_fields": {
            "hard_blocker_count": 0,
        },
    },
    {
        "artifact_id": "product_ai_report_explanation_packet_semantic_ready",
        "artifact_path": "runs/product_ai_report_explanation_packet_current.json",
        "builder_command": "python3 tools/build_product_ai_report_explanation_packet.py",
        "required_status": "product_ai_report_explanation_packet_ready",
        "required_true_fields": [
            "ai_report_explanation_packet_ready",
            "structured_customer_report_ready",
            "customer_report_delivery_contract_ready",
            "customer_report_evidence_binding_ready",
            "ligand_selection_rationale_ready",
        ],
    },
    {
        "artifact_id": "product_ai_report_ux_contract_semantic_ready",
        "artifact_path": "runs/product_ai_report_ux_contract_current.json",
        "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
        "required_status": "product_ai_report_ux_contract_ready",
        "required_true_fields": [
            "ai_report_ux_ready",
            "explanation_packet_ready",
            "customer_report_viewer_binding_ready",
            "binding_site_explanation_ready",
            "ligand_selection_rationale_ready",
            "uncertainty_narrative_ready",
        ],
    },
    {
        "artifact_id": "product_ledger_privacy_scan_semantic_ready",
        "artifact_path": "runs/product_ledger_privacy_scan_current.json",
        "builder_command": "python3 tools/build_product_ledger_privacy_scan.py",
        "required_status": "product_ledger_privacy_scan_ready",
        "required_true_fields": [
            "ledger_privacy_scan_ready",
        ],
    },
    {
        "artifact_id": "product_release_bundle_semantic_ready",
        "artifact_path": "runs/product_release_bundle_current.json",
        "builder_command": "python3 deploy/product_release_bundle.py",
        "required_status": "release_bundle_ready_for_operator_review",
        "required_true_fields": [
            "release_bundle_ready",
        ],
    },
    {
        "artifact_id": "product_pose_sampling_readiness_semantic_ready",
        "artifact_path": "runs/product_pose_sampling_readiness_current.json",
        "builder_command": "python3 tools/build_product_pose_sampling_readiness.py",
        "required_status": "product_pose_sampling_readiness_ready",
        "required_true_fields": [
            "pose_sampling_readiness_ready",
            "pose_generation_contract_ready",
            "pocket_detection_ready",
            "multi_start_pose_ensemble_ready",
            "pose_centroid_pocket_bound_ready",
            "pose_rmsd_diversity_surface_ready",
            "bounded_cross_docking_induced_fit_guard_ready",
            "pose_claim_boundary_guard_ready",
        ],
        "required_int_min_fields": {
            "cluster_count": 2,
        },
        "required_int_exact_fields": {
            "check_count": 6,
            "pass_count": 6,
            "blocker_count": 0,
            "requested_pose_start_count": 6,
            "pose_count": 6,
            "cross_docking_pose_count": 4,
            "execution_enabled": 0,
            "docking_results_emitted": 0,
            "external_state_mutated": 0,
            "claim_grade_pose_accuracy_ready": 0,
            "claim_grade_induced_fit_ready": 0,
            "claim_grade_cross_docking_ready": 0,
        },
        "required_text_exact_fields": {
            "pocket_method": "ligand_guided",
        },
    },
    {
        "artifact_id": "product_trajectory_sla_contract_semantic_ready",
        "artifact_path": "runs/product_trajectory_sla_contract_current.json",
        "builder_command": "python3 tools/build_product_trajectory_sla_contract.py",
        "required_status": "product_trajectory_sla_contract_ready",
        "required_true_fields": [
            "production_trajectory_sla_ready",
            "restricted_family_sla_allowed",
            "customer_sla_disclosure_ready",
            "restricted_sla_backed_by_historical_profile_artifacts",
        ],
        "required_int_min_fields": {
            "candidate_artifact_count": 1,
            "ready_run_count": 3,
            "qualified_ready_run_count": 3,
            "min_throughput_rows_per_sec": 1,
        },
        "required_int_exact_fields": {
            "minimum_ready_run_count": 3,
            "minimum_ready_rows_per_family": 10000,
            "broad_platform_sla_allowed": 0,
            "general_platform_sla_allowed": 0,
            "current_rocm_baseline_supports_restricted_family_sla": 0,
            "current_rocm_baseline_supports_broad_platform_sla": 0,
            "execution_enabled": 0,
            "benchmark_executed": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "sla_claim_tier": "restricted_family_sla",
            "current_rocm_baseline_claim_scope": "single_target_gpcr_baseline",
        },
    },
    {
        "artifact_id": "product_job_orchestration_contract_semantic_ready",
        "artifact_path": "runs/product_job_orchestration_contract_current.json",
        "builder_command": "python3 tools/build_product_job_orchestration_contract.py",
        "required_status": "product_job_orchestration_contract_ready",
        "required_true_fields": [
            "product_job_orchestration_contract_ready",
            "queue_lifecycle_progress_ready",
            "customer_run_history_lineage_ready",
            "status_snapshot_persistence_ready",
            "retention_policy_ready",
            "rerun_manifest_ready",
            "long_running_status_persistence_ready",
            "worker_backend_contract_ready",
            "worker_lease_heartbeat_ready",
            "retryable_failure_resume_ready",
            "running_cancel_ack_ready",
            "stale_worker_lease_recovery_ready",
            "stale_worker_lease_sweep_ready",
        ],
        "required_int_exact_fields": {
            "check_count": 12,
            "ready_check_count": 12,
            "blocked_check_count": 0,
            "stale_worker_lease_detected_count": 1,
            "stale_worker_lease_updated_count": 1,
            "retryable_after_stale_count": 1,
            "stale_worker_lease_timeout_seconds": 1800,
            "job_retention_days": 90,
            "execution_enabled": 0,
            "docking_results_emitted": 0,
            "external_state_mutated": 0,
        },
    },
    {
        "artifact_id": "product_goal_completion_audit_full_commercial_release_blockers_semantic_ready",
        "artifact_path": "runs/product_goal_completion_audit_current.json",
        "builder_command": "python3 tools/build_product_goal_completion_audit.py",
        "required_status": "blocked_product_goal_completion_audit",
        "required_true_fields": [
            "commercial_independence_ready",
            "restricted_delivery_complete",
        ],
        "required_int_exact_fields": {
            "release_blocker_fail_count": 2,
        },
        "required_text_exact_fields": {
            "primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "primary_release_blocker_tier": "full_commercial_scope",
            "primary_release_blocker": "full_scope_claim_closure_not_ready",
        },
    },
    {
        "artifact_id": "api_runner_profile_promotion_operator_receipt_blocked_semantic_ready",
        "artifact_path": "runs/api_runner_profile_promotion_operator_receipt_current.json",
        "builder_command": "python3 tools/build_api_runner_profile_promotion_operator_receipt.py",
        "required_status": "blocked_api_runner_profile_promotion_operator_receipt",
        "required_true_fields": [],
        "required_int_exact_fields": {
            "operator_receipt_ready": 0,
            "profile_count": 4,
            "receipt_row_count": 4,
            "pass_row_count": 0,
            "blocked_row_count": 4,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_API_RUNNER_PROFILE_PROMOTION",
            "first_blocked_profile_id": "backmapping_scoring.example",
            "first_blocked_row_blocker": "operator_decision_missing",
            "most_common_row_blocker": "operator_decision_missing",
        },
    },
    {
        "artifact_id": "cameo_validation_operations_dossier_current_bottleneck_semantic_ready",
        "artifact_path": "runs/cameo_validation_operations_dossier_current.json",
        "builder_command": "python3 tools/build_cameo_validation_operations_dossier.py",
        "required_status": "blocked_cameo_validation_operations_dossier",
        "required_true_fields": [
            "validation_ready",
            "official_results_intake_ready",
            "official_model1_result_ready",
            "official_cameo_results_used",
            "evidence_integrity_ready",
            "official_results_pending_honest",
            "no_local_native_accuracy_substitution",
            "external_mutation_flags_clear",
            "outbound_email_draft_ready",
            "outbound_email_send_preflight_ready",
            "outbound_email_send_preflight_authorized",
            "public_registration_allowed",
        ],
        "required_int_exact_fields": {
            "blocked_stage_count": 1,
            "approval_required_stage_count": 1,
            "approval_token_count": 2,
            "operator_input_required_count": 0,
            "operator_input_blocker_count": 0,
            "official_result_required": 0,
            "official_result_fetch_preflight_ready": 0,
            "official_result_fetch_preflight_authorized": 0,
            "official_result_fetch_preflight_network_request_opened": 0,
            "official_result_fetch_preflight_results_fetched": 0,
            "first_blocked_stage_blocker_count": 2,
            "outbound_email_enabled": 0,
            "native_local_accuracy_used": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "first_blocked_stage_id": "official_result_fetch_preflight",
            "first_blocked_stage_source_status": "blocked_cameo_official_result_fetch_preflight",
            "first_blocked_stage_artifact": "runs/cameo_official_result_fetch_preflight_current.json",
            "first_approval_required_stage_id": "public_registration_and_email",
            "first_approval_required_stage_source_status": "cameo_public_registration_preflight_ready",
            "first_approval_required_stage_artifact": "runs/cameo_capability_preflight_current.json",
            "first_approval_required_stage_token_required": (
                "APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL"
            ),
            "official_result_fetch_preflight_status": "blocked_cameo_official_result_fetch_preflight",
            "outbound_email_send_preflight_status": "cameo_outbound_email_send_preflight_ready",
            "receiver_smoke_status": "cameo_receiver_smoke_ready",
            "api_dependency_status": "cameo_api_dependency_ready",
        },
    },
    {
        "artifact_id": "cameo_official_result_fetch_preflight_blocked_semantic_ready",
        "artifact_path": "runs/cameo_official_result_fetch_preflight_current.json",
        "builder_command": "python3 tools/build_cameo_official_result_fetch_preflight.py",
        "required_status": "blocked_cameo_official_result_fetch_preflight",
        "required_true_fields": [
            "operations_surface_ready",
            "receiver_smoke_ready",
        ],
        "required_int_exact_fields": {
            "operator_fetch_csv_present": 0,
            "authorized_for_separate_operator_fetch": 0,
            "network_request_opened": 0,
            "official_results_fetched": 0,
            "native_local_accuracy_used": 0,
            "external_state_mutated": 0,
            "blocker_count": 2,
            "blocked_row_count": 1,
            "awaiting_operator_fetch_approval_row_count": 1,
        },
        "required_text_exact_fields": {
            "operator_fetch_csv": "runs/cameo_official_result_fetch_operator_approval_intake.csv",
            "operator_template_csv": "runs/cameo_official_result_fetch_operator_approval_template_current.csv",
            "fetch_approval_token_required": "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH",
        },
    },
    {
        "artifact_id": "product_production_ai_checkpoint_shadow_blocked_semantic_ready",
        "artifact_path": "runs/product_production_ai_checkpoint_readiness_current.json",
        "builder_command": "python3 tools/build_product_production_ai_checkpoint_readiness.py",
        "required_status": "blocked_product_production_ai_checkpoint_readiness",
        "required_true_fields": [
            "product_model_layer_ready",
            "production_gpu_execution_environment_ready",
            "force_gpu_worker_return_receipt_ready",
            "delta_force_derivation_validation_ready",
            "checkpoint_preflight_ready",
            "selected_sidecar_ready",
        ],
        "required_int_exact_fields": {
            "production_ai_checkpoint_ready": 0,
            "production_ai_inference_subject_active": 0,
            "production_promotion_allowed": 0,
            "trained_model_checkpoint_count": 0,
            "production_inference_acceptance_blocked_stage_count": 1,
        },
        "required_text_exact_fields": {
            "default_residual_mode": "shadow",
            "production_inference_actionable_blocker_stage_id": "registry_guarded_promotion_acceptance",
        },
    },
    {
        "artifact_id": "product_production_ai_promotion_workbench_shadow_blocked_semantic_ready",
        "artifact_path": "runs/product_production_ai_promotion_workbench_current.json",
        "builder_command": "python3 tools/build_product_production_ai_promotion_workbench.py",
        "required_status": "blocked_product_production_ai_promotion_workbench",
        "required_true_fields": [
            "promotion_workbench_ready",
        ],
        "required_int_exact_fields": {
            "production_ai_promotion_ready": 0,
            "production_ai_checkpoint_ready": 0,
            "production_ai_inference_subject_active": 0,
            "production_promotion_allowed": 0,
            "trained_model_checkpoint_count": 0,
            "post_return_promotion_ladder_blocked_stage_count": 2,
        },
        "required_text_exact_fields": {
            "default_residual_mode": "shadow",
            "first_blocked_stage_id": "residual_model_registry",
        },
    },
    {
        "artifact_id": "production_ai_registry_promotion_operator_receipt_blocked_semantic_ready",
        "artifact_path": "runs/production_ai_registry_promotion_operator_receipt_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
        "required_status": "blocked_production_ai_registry_promotion_operator_receipt",
        "required_true_fields": [
            "receipt_present",
            "registry_artifact_present",
            "checkpoint_readiness_artifact_present",
        ],
        "required_int_exact_fields": {
            "operator_receipt_ready": 0,
            "receipt_row_count": 1,
            "pass_row_count": 0,
            "blocked_row_count": 1,
            "blocker_count": 1,
            "observed_registry_trained_model_checkpoint_count": 0,
            "observed_checkpoint_registry_promotion_currently_satisfied": 0,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "first_blocked_artifact_id": "residual_model_registry_guarded_promotion",
            "first_blocked_row_blocker": "operator_placeholders_unfilled",
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "observed_registry_default_residual_mode": "shadow",
        },
    },
    {
        "artifact_id": "production_ai_registry_promotion_priority_packet_blocked_semantic_ready",
        "artifact_path": "runs/production_ai_registry_promotion_priority_packet_current.json",
        "builder_command": "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
        "required_status": "blocked_production_ai_registry_promotion_priority_packet",
        "required_true_fields": [
            "priority_packet_ready",
            "operator_receipt_csv_present",
            "operator_receipt_artifact_present",
            "residual_registry_artifact_present",
            "checkpoint_readiness_artifact_present",
            "promotion_workbench_artifact_present",
        ],
        "required_int_exact_fields": {
            "registry_promotion_ready": 0,
            "operator_receipt_ready": 0,
            "priority_item_count": 4,
            "operator_input_required_count": 4,
            "blocked_priority_item_count": 4,
            "required_gate_count": 4,
            "registry_promotion_missing_gate_count": 4,
            "observed_registry_trained_model_checkpoint_count": 0,
            "observed_registry_production_promotion_allowed": 0,
            "observed_registry_customer_facing_mutation_flags_ready": 0,
            "observed_checkpoint_registry_promotion_currently_satisfied": 0,
            "approval_token_count": 1,
            "model_promoted": 0,
            "customer_facing_mutation_enabled": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "operator_receipt_status": "blocked_production_ai_registry_promotion_operator_receipt",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "top_gate_id": "trained_model_checkpoint_count_positive",
            "top_priority_bucket": "trained_checkpoint_registration_required",
            "top_acceptance_artifact": "runs/residual_model_registry_current.json",
            "observed_registry_default_residual_mode": "shadow",
        },
    },
    {
        "artifact_id": "product_scope_breadth_evidence_receipt_blocked_semantic_ready",
        "artifact_path": "runs/product_scope_breadth_evidence_receipt_current.json",
        "builder_command": "python3 tools/build_product_scope_breadth_evidence_receipt.py",
        "required_status": "blocked_product_scope_breadth_evidence_receipt",
        "required_true_fields": [
            "receipt_csv_present",
            "scope_checklist_present",
        ],
        "required_int_exact_fields": {
            "full_scope_evidence_receipt_ready": 0,
            "receipt_row_count": 6,
            "pass_row_count": 0,
            "blocked_row_count": 6,
            "blocker_count": 1,
            "evidence_artifact_present_count": 0,
            "evidence_status_verified_count": 0,
            "required_scope_blocker_count": 6,
            "missing_required_scope_blocker_count": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
            "receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "first_blocked_observed_evidence_status": "missing",
            "most_common_row_blocker": "operator_placeholders_unfilled",
        },
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_receipt_blocked_semantic_ready",
        "artifact_path": "runs/engine_refinement_claim_evidence_receipt_current.json",
        "builder_command": "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py",
        "required_status": "blocked_engine_refinement_claim_evidence_receipt",
        "required_true_fields": [
            "receipt_csv_present",
        ],
        "required_int_exact_fields": {
            "claim_promotion_evidence_receipt_ready": 0,
            "receipt_row_count": 6,
            "pass_row_count": 0,
            "blocked_row_count": 6,
            "blocker_count": 1,
            "evidence_artifact_present_count": 0,
            "evidence_status_verified_count": 0,
            "required_blocker_count": 6,
            "missing_required_blocker_count": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "first_blocked_blocker_id": "public_benchmark_gate_not_ready",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
            "first_blocked_observed_evidence_status": "missing",
            "most_common_row_blocker": "operator_placeholders_unfilled",
        },
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_priority_packet_blocked_semantic_ready",
        "artifact_path": "runs/engine_refinement_claim_evidence_priority_packet_current.json",
        "builder_command": "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
        "required_status": "blocked_engine_refinement_claim_evidence_priority_packet",
        "required_true_fields": [
            "priority_packet_ready",
            "public_benchmark_work_order_present",
        ],
        "required_int_exact_fields": {
            "claim_promotion_allowed": 0,
            "priority_item_count": 6,
            "operator_input_required_count": 6,
            "blocked_priority_item_count": 6,
            "required_blocker_count": 6,
            "missing_required_blocker_count": 0,
            "public_benchmark_gate_ready": 0,
            "public_benchmark_work_order_row_count": 8,
            "public_benchmark_work_order_apply_ready": 0,
            "public_benchmark_work_order_apply_blocked_row_count": 8,
            "approval_token_count": 1,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
        },
    },
    {
        "artifact_id": "product_full_commercial_blocker_evidence_matrix_semantic_ready",
        "artifact_path": "runs/product_full_commercial_blocker_evidence_matrix_current.json",
        "builder_command": "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
        "required_status": "blocked_product_full_commercial_blocker_evidence_matrix",
        "required_true_fields": [
            "release_blocker_visibility_ready",
        ],
        "required_int_exact_fields": {
            "blocked_matrix_row_count": 12,
            "approval_token_count": 2,
            "scope_receipt_blocked_row_count": 6,
            "engine_receipt_blocked_row_count": 6,
        },
        "required_text_exact_fields": {
            "first_blocked_release_blocker_id": "R8_full_scope_claim_closure",
            "first_blocked_evidence_row_id": "direct_binding_evidence_missing",
            "first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "first_blocked_observed_evidence_status": "missing",
            "scope_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
            "engine_receipt_most_common_row_blocker": "operator_placeholders_unfilled",
        },
    },
    {
        "artifact_id": "goal_operator_action_board_primary_release_blocker_semantic_ready",
        "artifact_path": "runs/goal_operator_action_board_current.json",
        "builder_command": "python3 tools/build_goal_operator_action_board.py",
        "required_status": "operator_actions_required",
        "required_true_fields": [],
        "required_int_exact_fields": {
            "product_goal_release_blocker_fail_count": 2,
        },
        "required_text_exact_fields": {
            "product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "product_goal_primary_release_blocker_tier": "full_commercial_scope",
            "product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_release_blocker_action_id": (
                "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
            ),
            "primary_release_blocker_action_required_input": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_release_blocker_action_status": "required",
        },
    },
    {
        "artifact_id": "goal_operator_intake_kit_primary_release_blocker_semantic_ready",
        "artifact_path": "runs/goal_operator_intake_kit_current/manifest.json",
        "builder_command": "python3 tools/build_goal_operator_intake_kit.py",
        "required_status": "goal_operator_intake_kit_ready",
        "required_true_fields": [],
        "required_int_exact_fields": {
            "product_goal_release_blocker_fail_count": 2,
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
        },
        "required_text_exact_fields": {
            "product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "product_goal_primary_release_blocker_tier": "full_commercial_scope",
            "product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_release_blocker_action_id": (
                "product_scope_expansion:resolve_full_scope_breadth_evidence_receipt"
            ),
            "primary_release_blocker_action_required_input": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "primary_release_blocker_action_status": "required",
            "full_commercial_evidence_receipt_source_gate_statuses": (
                "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
                "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
            ),
            "full_commercial_evidence_receipt_required_inputs": (
                "config/product_scope_breadth_evidence_receipt_current.csv;"
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "full_commercial_evidence_receipt_approval_tokens": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
        },
    },
    {
        "artifact_id": "goal_api_surface_contract_semantic_ready",
        "artifact_path": "runs/goal_api_surface_contract_current.json",
        "builder_command": "python3 tools/build_goal_api_surface_contract.py",
        "required_status": "goal_api_surface_contract_ready",
        "required_true_fields": [
            "surface_ready",
        ],
        "required_int_exact_fields": {
            "blocker_count": 0,
            "missing_status_key_count": 0,
            "missing_full_commercial_visibility_token_count": 0,
            "missing_fail_closed_flag_count": 0,
        },
    },
    {
        "artifact_id": "goal_bottleneck_briefing_semantic_ready",
        "artifact_path": "runs/goal_bottleneck_briefing_current.json",
        "builder_command": "python3 tools/build_goal_bottleneck_briefing.py",
        "required_status": "goal_bottleneck_briefing_ready",
        "required_true_fields": [],
        "required_int_exact_fields": {
            "completion_audit_release_blocker_bottleneck_count": 2,
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
        },
        "required_text_exact_fields": {
            "full_commercial_evidence_receipt_source_gate_statuses": (
                "product_scope_breadth_evidence_receipt=blocked_product_scope_breadth_evidence_receipt;"
                "engine_refinement_claim_evidence_receipt=blocked_engine_refinement_claim_evidence_receipt"
            ),
            "full_commercial_evidence_receipt_required_inputs": (
                "config/product_scope_breadth_evidence_receipt_current.csv;"
                "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
            ),
            "full_commercial_evidence_receipt_approval_tokens": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT;"
                "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
            ),
        },
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json_if_present(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file_if_present(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _mtime(path_like: str | Path, *, root: Path = ROOT) -> float:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return 0.0
    return path.stat().st_mtime


def _iso_from_mtime(value: float) -> str:
    if value <= 0:
        return ""
    return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc).isoformat(timespec="seconds")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    if packet.get("status"):
        return packet
    return {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _artifact_row(spec: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    artifact_path = _text(spec.get("artifact_path"))
    depends_on = [_text(item) for item in spec.get("depends_on") or [] if _text(item)]
    artifact = _resolve(artifact_path, root=root)
    artifact_present = artifact.is_file()
    artifact_mtime = _mtime(artifact_path, root=root)
    missing_dependencies = [path for path in depends_on if not _resolve(path, root=root).exists()]
    stale_dependencies = [
        path
        for path in depends_on
        if _resolve(path, root=root).exists() and artifact_mtime > 0 and _mtime(path, root=root) > artifact_mtime
    ]
    if depends_on:
        newest_dependency_mtime = max((_mtime(path, root=root) for path in depends_on if _resolve(path, root=root).exists()), default=0.0)
    else:
        newest_dependency_mtime = 0.0
    passed = artifact_present and not missing_dependencies and not stale_dependencies
    return {
        "row_type": "artifact_freshness",
        "artifact_id": _text(spec.get("artifact_id")),
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "builder_command": _text(spec.get("builder_command")),
        "artifact_present": artifact_present,
        "artifact_mtime_utc": _iso_from_mtime(artifact_mtime),
        "artifact_sha256": _sha256_file_if_present(artifact_path, root=root),
        "dependency_count": len(depends_on),
        "newest_dependency_mtime_utc": _iso_from_mtime(newest_dependency_mtime),
        "missing_dependency_count": len(missing_dependencies),
        "missing_dependency_paths": missing_dependencies,
        "stale_dependency_count": len(stale_dependencies),
        "stale_dependency_paths": stale_dependencies,
        "observed": (
            f"present={artifact_present};dependencies={len(depends_on)};"
            f"missing_dependencies={len(missing_dependencies)};stale_dependencies={len(stale_dependencies)}"
        ),
        "required": "artifact exists and is not older than any listed source/dependency artifact",
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _status_row(spec: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    artifact_path = _text(spec.get("artifact_path"))
    packet = _read_json_if_present(artifact_path, root=root)
    summary = _summary(packet)
    required_status = _text(spec.get("required_status"))
    required_true_fields = [_text(item) for item in spec.get("required_true_fields") or [] if _text(item)]
    missing_true_fields = [field for field in required_true_fields if summary.get(field) is not True]
    required_int_min_fields = {
        _text(field): _int(value)
        for field, value in (spec.get("required_int_min_fields") or {}).items()
        if _text(field)
    }
    required_int_exact_fields = {
        _text(field): _int(value)
        for field, value in (spec.get("required_int_exact_fields") or {}).items()
        if _text(field)
    }
    required_text_exact_fields = {
        _text(field): _text(value)
        for field, value in (spec.get("required_text_exact_fields") or {}).items()
        if _text(field)
    }
    failed_int_min_fields = [
        field
        for field, minimum in required_int_min_fields.items()
        if field not in summary or _int(summary.get(field)) < minimum
    ]
    failed_int_exact_fields = [
        field
        for field, expected in required_int_exact_fields.items()
        if field not in summary or _int(summary.get(field)) != expected
    ]
    failed_text_exact_fields = [
        field
        for field, expected in required_text_exact_fields.items()
        if field not in summary or _text(summary.get(field)) != expected
    ]
    status_matches = _text(summary.get("status")) == required_status
    passed = (
        bool(summary)
        and status_matches
        and not missing_true_fields
        and not failed_int_min_fields
        and not failed_int_exact_fields
        and not failed_text_exact_fields
    )
    return {
        "row_type": "artifact_semantic_status",
        "artifact_id": _text(spec.get("artifact_id")),
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "builder_command": _text(spec.get("builder_command")),
        "artifact_present": bool(packet),
        "artifact_mtime_utc": _iso_from_mtime(_mtime(artifact_path, root=root)),
        "artifact_sha256": _sha256_file_if_present(artifact_path, root=root),
        "dependency_count": 0,
        "newest_dependency_mtime_utc": "",
        "missing_dependency_count": 0 if packet else 1,
        "missing_dependency_paths": [] if packet else [artifact_path],
        "stale_dependency_count": 0,
        "stale_dependency_paths": [],
        "required_status": required_status,
        "observed_status": _text(summary.get("status")) or "missing",
        "required_true_fields": required_true_fields,
        "missing_true_fields": missing_true_fields,
        "missing_true_field_count": len(missing_true_fields),
        "required_int_min_fields": required_int_min_fields,
        "failed_int_min_fields": failed_int_min_fields,
        "failed_int_min_field_count": len(failed_int_min_fields),
        "required_int_exact_fields": required_int_exact_fields,
        "failed_int_exact_fields": failed_int_exact_fields,
        "failed_int_exact_field_count": len(failed_int_exact_fields),
        "required_text_exact_fields": required_text_exact_fields,
        "failed_text_exact_fields": failed_text_exact_fields,
        "failed_text_exact_field_count": len(failed_text_exact_fields),
        "observed": (
            f"status={_text(summary.get('status')) or 'missing'};"
            f"required_status={required_status};missing_true_fields={len(missing_true_fields)};"
            f"failed_int_min_fields={len(failed_int_min_fields)};"
            f"failed_int_exact_fields={len(failed_int_exact_fields)};"
            f"failed_text_exact_fields={len(failed_text_exact_fields)}"
        ),
        "required": (
            f"status={required_status};"
            f"required_true_fields={','.join(required_true_fields) or 'none'};"
            f"required_int_min_fields={','.join(required_int_min_fields) or 'none'};"
            f"required_int_exact_fields={','.join(required_int_exact_fields) or 'none'};"
            f"required_text_exact_fields={','.join(required_text_exact_fields) or 'none'}"
        ),
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _readme_accuracy_rows(
    *,
    root: Path = ROOT,
    accuracy_path: str = "runs/accuracy_parity_scorecard_current.json",
    readme_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    if readme_paths is None:
        readme_paths = ["README.md", "README.ko.md"]
    packet = _read_json_if_present(accuracy_path, root=root)
    summary = _summary(packet)
    status = _text(summary.get("status"))
    row_count = _int(summary.get("row_count"))
    pass_count = _int(summary.get("pass_row_count"))
    restricted_pass_count = _int(summary.get("restricted_pass_row_count"))
    blocked_count = _int(summary.get("blocked_row_count"))
    missing_count = _int(summary.get("missing_row_count"))
    required_fragments = [
        f"status={status}",
        f"pass={pass_count}",
        f"restricted_pass={restricted_pass_count}",
        f"blocked={blocked_count}",
    ]
    if missing_count:
        required_fragments.append(f"missing={missing_count}")
    obsolete_fragments: list[str] = []
    if row_count and restricted_pass_count and pass_count != row_count:
        obsolete_fragments.extend([f"pass={row_count}", f"pass={row_count}/{row_count}"])
    rows: list[dict[str, Any]] = []
    for readme_path in readme_paths:
        path = _resolve(readme_path, root=root)
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        missing_required = [fragment for fragment in required_fragments if fragment not in text]
        obsolete_present = [fragment for fragment in obsolete_fragments if fragment in text]
        passed = bool(summary) and path.is_file() and not missing_required and not obsolete_present
        rows.append(
            {
                "row_type": "readme_metric_drift",
                "artifact_id": f"readme_accuracy_parity:{readme_path}",
                "status": "pass" if passed else "fail",
                "artifact_path": readme_path,
                "builder_command": "manual README update from runs/accuracy_parity_scorecard_current.json",
                "artifact_present": path.is_file(),
                "artifact_mtime_utc": _iso_from_mtime(_mtime(readme_path, root=root)),
                "artifact_sha256": _sha256_file_if_present(readme_path, root=root),
                "dependency_count": 1,
                "newest_dependency_mtime_utc": _iso_from_mtime(_mtime(accuracy_path, root=root)),
                "missing_dependency_count": 0 if summary else 1,
                "missing_dependency_paths": [] if summary else [accuracy_path],
                "stale_dependency_count": 0,
                "stale_dependency_paths": [],
                "missing_required_fragments": missing_required,
                "obsolete_fragments_present": obsolete_present,
                "observed": (
                    f"accuracy_status={status or 'missing'};pass={pass_count};"
                    f"restricted_pass={restricted_pass_count};blocked={blocked_count};"
                    f"missing_required={len(missing_required)};obsolete_present={len(obsolete_present)}"
                ),
                "required": ";".join(required_fragments),
                "release_blocker": not passed,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return rows


def build_product_release_source_of_truth_gate(
    *,
    root: str | Path = ROOT,
    artifact_specs: list[dict[str, Any]] | None = None,
    status_specs: list[dict[str, Any]] | None = None,
    readme_paths: list[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    artifact_spec_rows = artifact_specs if artifact_specs is not None else DEFAULT_ARTIFACT_SPECS
    status_spec_rows = (
        status_specs
        if status_specs is not None
        else DEFAULT_STATUS_SPECS
        if artifact_specs is None
        else []
    )
    rows = [
        _artifact_row(spec, root=root_path)
        for spec in artifact_spec_rows
    ]
    rows.extend(_status_row(spec, root=root_path) for spec in status_spec_rows)
    rows.extend(_readme_accuracy_rows(root=root_path, readme_paths=readme_paths))
    blockers = [row for row in rows if row["release_blocker"]]
    artifact_rows = [row for row in rows if row["row_type"] == "artifact_freshness"]
    status_rows = [row for row in rows if row["row_type"] == "artifact_semantic_status"]
    readme_rows = [row for row in rows if row["row_type"] == "readme_metric_drift"]
    ready = not blockers
    summary = {
        "packet_type": "product_release_source_of_truth_gate",
        "status": "product_release_source_of_truth_gate_ready" if ready else "blocked_product_release_source_of_truth_gate",
        "release_source_of_truth_ready": ready,
        "row_count": len(rows),
        "artifact_row_count": len(artifact_rows),
        "semantic_status_row_count": len(status_rows),
        "readme_row_count": len(readme_rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "missing_artifact_count": sum(1 for row in artifact_rows if not row["artifact_present"]),
        "missing_dependency_count": sum(int(row["missing_dependency_count"]) for row in artifact_rows),
        "stale_artifact_count": sum(1 for row in artifact_rows if int(row["stale_dependency_count"]) > 0),
        "semantic_status_blocker_count": sum(1 for row in status_rows if row["release_blocker"]),
        "readme_drift_count": sum(1 for row in readme_rows if row["release_blocker"]),
        "blocked_artifact_ids": [row["artifact_id"] for row in blockers],
        "release_refresh_command_count": len(RELEASE_REFRESH_COMMANDS),
        "release_refresh_commands": list(RELEASE_REFRESH_COMMANDS),
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Source-of-truth gate is ready; release decision may consume these current artifacts."
            if ready
            else "Run python3 tools/run_product_release_current_refresh.py --execute, then rerun the source-of-truth and release decision gates."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Product Release Source Of Truth Gate",
        "",
        f"- status: `{s['status']}`",
        f"- release_source_of_truth_ready: `{s['release_source_of_truth_ready']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- stale_artifact_count: `{s['stale_artifact_count']}`",
        f"- semantic_status_blocker_count: `{s['semantic_status_blocker_count']}`",
        f"- readme_drift_count: `{s['readme_drift_count']}`",
        f"- release_refresh_command_count: `{s['release_refresh_command_count']}`",
        "",
        "## Checks",
        "",
        "| type | artifact | status | observed | required |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['row_type']}` | `{row['artifact_id']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the product release source-of-truth freshness gate.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_product_release_source_of_truth_gate(root=root)
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
