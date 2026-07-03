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
R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
)
R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
)

CLAIM_BOUNDARY = (
    "Product release source-of-truth gate only; it checks local current artifact freshness, source/dependency "
    "ordering, and README metric drift. It does not run docking, execute GPU jobs, assemble bundles, submit "
    "external validation, upload, delete, email, commit, push, or mutate external state."
)

REFINE_TIER_PUBLIC_BENCHMARK_METRIC_MATERIALIZATION_COMMAND = (
    "python3 tools/product/materialize_refine_tier_public_benchmark_metric_sources.py "
    "--reviewed-at-utc 2026-06-14T00:00:00Z"
)
REFINE_TIER_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py "
    "--work-order-csv runs/refine_tier_public_benchmark_work_order_materialized_current.csv "
    "--metric-evidence-csv runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv "
    "--out-json runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json "
    "--out-csv runs/refine_tier_public_benchmark_intake_candidate_materialized_current.csv "
    "--out-md runs/refine_tier_public_benchmark_work_order_apply_materialized_current.md"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_work_order.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_CANDIDATE_QUEUE_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_candidate_queue.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_intake.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_PLAN_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_APPLY_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
    "--mode preview"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_templates.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_claim_grade_gap_audit.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_RESIDUAL_REMEDIATION_BOARD_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_residual_remediation_board.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_RESIDUAL_METRIC_PAYLOAD_PRIORITY_PACKET_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_residual_metric_payload_priority_packet.py"
)
REFINE_TIER_PUBLIC_BENCHMARK_SEEDED_METRIC_PAYLOAD_RECEIPT_BACKFILL_PACKET_COMMAND = (
    "python3 tools/product/build_refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet.py"
)
PRODUCT_PUBLIC_BENCHMARK_SCORECARD_INTAKE_SYNC_COMMAND = (
    "python3 tools/sync_product_public_benchmark_scorecard_intake.py"
)
PRODUCT_PUBLIC_BENCHMARK_CONTRACT_COMMAND = "python3 tools/build_product_public_benchmark_contract.py"
PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_COMMAND = "python3 tools/build_product_public_benchmark_work_order.py"
PUBLIC_BENCHMARK_PHASE2_HARNESS_AUDIT_COMMAND = (
    "python3 tools/product/build_public_benchmark_phase2_harness_audit.py"
)
BENCHMARK_LEDGER_COMMAND = "python3 tools/product/build_benchmark_ledger.py"
PUBLIC_BENCHMARK_VINA_GNINA_COMPARISON_WORK_ORDER_COMMAND = (
    "python3 tools/product/build_public_benchmark_vina_gnina_comparison_work_order.py"
)
PUBLIC_BENCHMARK_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_COMMAND = (
    "python3 tools/product/build_public_benchmark_vina_gnina_score_template_receipt.py"
)
PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_COMMAND = (
    "python3 tools/product/build_public_benchmark_external_receipts_audit.py"
)
PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_COMMAND = (
    "python3 tools/product/build_public_benchmark_receipt_attach_packet.py"
)
GPCR_HARD_DECOY_CLAIM_LOCK_REASON = (
    "ADORA2A neutral-antagonist rescue rule was discovered from the current failure slice; "
    "independent claim-unlock replay required before broad GPCR/router promotion."
)
GPCR_HARD_DECOY_CURRENT_FIT_CLOSURE_PROBE_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_current_fit_closure_probe.py"
)
GPCR_HARD_DECOY_ADORA2A_NEUTRAL_RESCUE_PROBE_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_adora2a_neutral_rescue_probe.py"
)
GPCR_HARD_DECOY_ADORA2A_PREREGISTERED_REPLAY_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_adora2a_preregistered_replay.py"
)
GPCR_HARD_DECOY_SUITE_CURRENT_INPUT_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_suite_current_input.py "
    "--preregistered-replay-json runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json"
)
GPCR_HARD_DECOY_SUITE_REPORT_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_suite_report.py "
    "--required-target-ids DRD2,HTR2A,OPRM1 "
    f"--claim-lock-reason '{GPCR_HARD_DECOY_CLAIM_LOCK_REASON}'"
)
GPCR_A1_INDEPENDENT_REPEAT_PACKET_COMMAND = (
    "python3 tools/build_gpcr_a1_independent_repeat_packet.py "
    "--ranking-json runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json "
    "--repeat-tag gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1"
)
GPCR_A1_ACCURACY_REPAIR_QUEUE_COMMAND = "python3 tools/build_gpcr_a1_accuracy_repair_queue.py"
GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py"
)
POCKETMD_LITE_STAGE3_CONTACT_CLASH_INTAKE_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py"
)
POCKETMD_LITE_REPORT_COMMAND = "python3 tools/product/build_pocketmd_lite_report.py"
POCKETMD_LITE_REFINEMENT_WORK_ORDER_COMMAND = "python3 tools/product/build_pocketmd_lite_refinement_work_order.py"
POCKETMD_LITE_REMAINING_EVIDENCE_QUEUE_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_remaining_evidence_queue.py"
)
POCKETMD_LITE_EVIDENCE_RECOVERY_MANIFEST_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_evidence_recovery_manifest.py"
)
POCKETMD_LITE_METRIC_COLLECTION_INPUT_PACK_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_metric_collection_input_pack.py"
)
POCKETMD_LITE_METRIC_COLLECTION_PROBE_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_metric_collection_probe.py"
)
POCKETMD_LITE_LIGAND_ATOM_FRAME_RECOVERY_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_ligand_atom_frame_recovery.py"
)
POCKETMD_LITE_BOUNDED_METRIC_COLLECTOR_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_bounded_metric_collector.py"
)
POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_claim_grade_metric_source_audit.py"
)
POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_candidate_metric_fill_preview.py"
)
POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_report.py "
    "--input-csv runs/pocketmd_lite_candidate_metric_fill_preview_current.candidates.csv "
    "--out-json runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json "
    "--out-md runs/pocketmd_lite_candidate_metric_fill_preview_report_current.md "
    "--out-csv runs/pocketmd_lite_candidate_metric_fill_preview_report_current.csv"
)
POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_COMMAND = (
    "python3 tools/product/build_pocketmd_lite_topk_refinement_audit.py"
)
HBOND_BACKMAP_REPORT_COMMAND = (
    "python3 tools/product/build_hbond_backmap_report.py "
    "--scores-csv runs/product_image_smoke_runner_artifacts/backmapping_scores.csv"
)
PRODUCT_OPERATOR_COCKPIT_COMMAND = "python3 tools/product/build_product_operator_cockpit.py"
SUPPORT_BUNDLE_COMMAND = "python3 tools/product/build_support_bundle.py"
ENTERPRISE_ON_PREM_READINESS_GATE_COMMAND = (
    "python3 tools/product/build_enterprise_on_prem_readiness_gate.py"
)
DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_COMMAND = (
    "python3 tools/product/build_developer_preview_final_gate_audit.py"
)

RELEASE_REFRESH_COMMANDS = [
    "python3 tools/build_accuracy_parity_scorecard.py",
    "python3 tools/build_residual_shadow_ab.py",
    "python3 tools/build_residual_model_registry.py",
    "python3 tools/build_residual_force_gpu_worker_return_manifest_finalize.py",
    "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
    "python3 tools/build_residual_force_derivation_validation.py",
    "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
    "python3 tools/build_residual_energy_force_label_validation.py",
    "python3 tools/build_residual_energy_force_label_evidence_work_order.py",
    "python3 tools/build_residual_production_training_data_contract.py",
    "python3 tools/build_product_production_ai_checkpoint_readiness.py",
    "python3 tools/build_product_production_ai_promotion_workbench.py",
    "python3 tools/build_production_ai_registry_promotion_operator_receipt.py",
    "python3 tools/product/build_production_ai_registry_promotion_priority_packet.py",
    "python3 tools/build_production_ai_registry_promotion_operator_field_worksheet.py",
    "python3 tools/build_production_ai_registry_promotion_operator_staging_apply.py",
    "python3 tools/build_product_scope_breadth_contract.py",
    "python3 tools/build_product_scope_breadth_closure_checklist.py",
    "python3 tools/build_product_scope_breadth_evidence_receipt.py",
    "python3 tools/build_product_scope_breadth_evidence_priority_packet.py",
    "python3 tools/build_product_scope_breadth_evidence_operator_field_worksheet.py",
    "python3 tools/build_product_scope_breadth_evidence_operator_staging_apply.py",
    "python3 tools/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py",
    "python3 tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py",
    (
        "python3 tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py "
        "--mode preview --staging-csv runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
    ),
    "python3 tools/build_aqp1_negative_evidence_intake_gate.py",
    "python3 tools/build_product_operational_quality_contract.py",
    "python3 scripts/verify_quality_gate.py --quiet --out-json runs/product_quality_gate_verification_current.json",
    "python3 tools/build_api_runner_profile_promotion_readiness.py",
    "python3 tools/build_api_runner_profile_promotion_operator_receipt.py",
    "python3 tools/product/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 420",
    "python3 tools/build_api_docking_dispatch_e2e_evidence.py",
    "python3 tools/build_product_job_orchestration_contract.py",
    PRODUCT_PUBLIC_BENCHMARK_SCORECARD_INTAKE_SYNC_COMMAND,
    PRODUCT_PUBLIC_BENCHMARK_CONTRACT_COMMAND,
    "python3 tools/build_architecture_validation_package_report.py",
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
    "python3 tools/product/build_ai_md_contract_source_of_truth_gate.py",
    "python3 tools/build_product_service_boundary_contract.py",
    PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_COMMAND,
    PUBLIC_BENCHMARK_PHASE2_HARNESS_AUDIT_COMMAND,
    BENCHMARK_LEDGER_COMMAND,
    PUBLIC_BENCHMARK_VINA_GNINA_COMPARISON_WORK_ORDER_COMMAND,
    PUBLIC_BENCHMARK_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_COMMAND,
    GPCR_HARD_DECOY_CURRENT_FIT_CLOSURE_PROBE_COMMAND,
    GPCR_HARD_DECOY_ADORA2A_NEUTRAL_RESCUE_PROBE_COMMAND,
    GPCR_HARD_DECOY_ADORA2A_PREREGISTERED_REPLAY_COMMAND,
    GPCR_HARD_DECOY_SUITE_CURRENT_INPUT_COMMAND,
    GPCR_HARD_DECOY_SUITE_REPORT_COMMAND,
    POCKETMD_LITE_STAGE3_CONTACT_CLASH_INTAKE_COMMAND,
    POCKETMD_LITE_REPORT_COMMAND,
    POCKETMD_LITE_REFINEMENT_WORK_ORDER_COMMAND,
    POCKETMD_LITE_REMAINING_EVIDENCE_QUEUE_COMMAND,
    POCKETMD_LITE_EVIDENCE_RECOVERY_MANIFEST_COMMAND,
    POCKETMD_LITE_METRIC_COLLECTION_INPUT_PACK_COMMAND,
    POCKETMD_LITE_LIGAND_ATOM_FRAME_RECOVERY_COMMAND,
    POCKETMD_LITE_BOUNDED_METRIC_COLLECTOR_COMMAND,
    POCKETMD_LITE_METRIC_COLLECTION_PROBE_COMMAND,
    POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_COMMAND,
    POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_COMMAND,
    POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_COMMAND,
    POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_COMMAND,
    "python3 tools/build_product_capability_surface_contract.py",
    "python3 tools/build_product_commercial_independence_gate.py",
    "python3 tools/build_product_image_smoke_preflight.py",
    HBOND_BACKMAP_REPORT_COMMAND,
    "python3 tools/build_product_end_to_end_rocm_benchmark.py",
    "python3 tools/build_ai_md_engine_kpi_report.py",
    "python3 tools/build_ai_md_product_evidence_bundle.py",
    "python3 tools/build_ai_md_engine_kpi_report.py",
    "python3 tools/build_ai_md_product_evidence_bundle.py",
    "python3 tools/build_ai_md_engine_kpi_report.py",
    "python3 tools/build_ai_md_product_evidence_bundle.py",
    "python3 tools/build_gpcr_commercial_phase_ab_closure_chain.py",
    GPCR_A1_INDEPENDENT_REPEAT_PACKET_COMMAND,
    "python3 tools/build_gpcr_active_scorer_promotion_decision_packet.py",
    "python3 tools/build_gpcr_broad_claim_review_receipt.py",
    "python3 tools/build_gpcr_broad_claim_scope_readiness.py",
    GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_COMMAND,
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
    REFINE_TIER_PUBLIC_BENCHMARK_METRIC_MATERIALIZATION_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_CANDIDATE_QUEUE_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_PLAN_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_APPLY_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_RESIDUAL_REMEDIATION_BOARD_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_RESIDUAL_METRIC_PAYLOAD_PRIORITY_PACKET_COMMAND,
    REFINE_TIER_PUBLIC_BENCHMARK_SEEDED_METRIC_PAYLOAD_RECEIPT_BACKFILL_PACKET_COMMAND,
    "python3 tools/product/build_engine_refinement_tier_readiness.py",
    "python3 tools/product/build_engine_refinement_claim_evidence_receipt.py",
    "python3 tools/product/build_engine_refinement_claim_evidence_priority_packet.py",
    PUBLIC_BENCHMARK_VINA_GNINA_COMPARISON_WORK_ORDER_COMMAND,
    PUBLIC_BENCHMARK_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_COMMAND,
    PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_COMMAND,
    PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_COMMAND,
    "python3 tools/build_engine_refinement_claim_evidence_operator_field_worksheet.py",
    "python3 tools/build_engine_refinement_claim_evidence_operator_staging_apply.py",
    "python3 tools/product/build_science_accuracy_frontier.py",
    "python3 tools/product/build_product_launch_r4_preflight.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_release_operations_dossier.py",
    "python3 tools/build_product_architecture_contract.py",
    "python3 tools/build_cameo_official_result_fetch_preflight.py",
    "python3 tools/build_cameo_public_registration_approval_gate.py",
    "python3 tools/build_cameo_outbound_email_send_preflight.py",
    "python3 tools/build_cameo_validation_operations_dossier.py",
    "python3 tools/build_cameo_architecture_validation_contract.py",
    DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_COMMAND,
    "python3 tools/build_goal_readiness_rollup.py",
    "python3 tools/build_product_release_source_of_truth_gate.py",
    "python3 tools/build_goal_release_decision_gate.py",
    "python3 tools/build_product_goal_completion_audit.py",
    "python3 tools/build_goal_operator_action_board.py",
    PRODUCT_OPERATOR_COCKPIT_COMMAND,
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
    "python3 tools/build_api_runner_profile_promotion_operator_staging_apply.py",
    "python3 tools/build_master_gap_closure_rollup.py",
    "python3 tools/build_product_ledger_privacy_scan.py",
    SUPPORT_BUNDLE_COMMAND,
    ENTERPRISE_ON_PREM_READINESS_GATE_COMMAND,
    "python3 tools/build_product_release_source_of_truth_gate.py",
    "python3 tools/build_goal_release_decision_gate.py",
    "python3 tools/build_goal_operator_action_board.py",
    PRODUCT_OPERATOR_COCKPIT_COMMAND,
    "python3 tools/build_goal_release_burndown_work_order.py",
    "python3 tools/build_goal_operator_intake_kit.py",
    "python3 tools/build_goal_bottleneck_briefing.py",
    "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_rollout_execution_readiness.py",
    "python3 tools/product/build_product_launch_r4_preflight.py",
    "python3 tools/build_product_rollout_execution_smoke_receipt.py",
    "python3 tools/build_deploy_ops_legal_gap_closure.py",
    "python3 tools/build_master_gap_closure_rollup.py",
    "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
    "python3 tools/build_product_ledger_privacy_scan.py",
    SUPPORT_BUNDLE_COMMAND,
    ENTERPRISE_ON_PREM_READINESS_GATE_COMMAND,
    PRODUCT_OPERATOR_COCKPIT_COMMAND,
    "python3 tools/build_product_release_source_of_truth_gate.py",
    "python3 tools/build_goal_release_decision_gate.py",
    "python3 tools/build_goal_operator_action_board.py",
    PRODUCT_OPERATOR_COCKPIT_COMMAND,
    "python3 tools/build_goal_operator_intake_kit.py",
    "python3 tools/build_goal_bottleneck_briefing.py",
    "python3 tools/build_product_full_commercial_blocker_evidence_matrix.py",
    "python3 deploy/product_release_bundle.py",
    "python3 tools/build_product_rollout_execution_readiness.py",
    "python3 tools/product/build_product_launch_r4_preflight.py",
    "python3 tools/build_product_rollout_execution_smoke_receipt.py",
    "python3 tools/build_deploy_ops_legal_gap_closure.py",
    "python3 tools/build_master_gap_closure_rollup.py",
    "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
    "python3 tools/build_product_ledger_privacy_scan.py",
    SUPPORT_BUNDLE_COMMAND,
    ENTERPRISE_ON_PREM_READINESS_GATE_COMMAND,
    PRODUCT_OPERATOR_COCKPIT_COMMAND,
    "python3 tools/build_product_release_source_of_truth_gate.py",
]

DEFAULT_ARTIFACT_SPECS: list[dict[str, Any]] = [
    {
        "artifact_id": "accuracy_parity_scorecard",
        "artifact_path": "runs/accuracy_parity_scorecard_current.json",
        "builder_command": "python3 tools/build_accuracy_parity_scorecard.py",
        "depends_on": [
            "tools/accounting/build_accuracy_parity_scorecard.py",
            "tools/build_accuracy_parity_scorecard.py",
            "tools/lib/artifacts.py",
            "runs/accuracy_gate_local_delivery_preflight_current.json",
            "runs/openmm_2bead_strict_multitarget_current_accuracy_external.json",
            "runs/openmm_2bead_strict_multitarget_current_long_stability_validation.json",
            "runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json",
            "runs/gpcr_core_rank_diagnostics_current.json",
            "runs/gpcr_drd2_pose_generation_repair_packet_current.json",
            "runs/gpcr_drd2_atom_typed_backmapping_support_current.json",
            "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json",
            "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.json",
            "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json",
            "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.json",
            "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json",
            "runs/gpcr_conditional_prior_promotion_gate_current.json",
            "runs/structure_refinement_scorecard_current.json",
            "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json",
            "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json",
            "runs/commercialization_readiness_current.json",
        ],
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
            "runs/residual_production_checkpoint_work_order_current.json",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
        ],
    },
    {
        "artifact_id": "product_production_ai_checkpoint_readiness",
        "artifact_path": "runs/product_production_ai_checkpoint_readiness_current.json",
        "builder_command": "python3 tools/build_product_production_ai_checkpoint_readiness.py",
        "depends_on": [
            "tools/accounting/build_product_production_ai_checkpoint_readiness.py",
            "tools/build_product_production_ai_checkpoint_readiness.py",
            "betelgeuze_product/production_ai_checkpoint_readiness.py",
            "runs/residual_model_registry_current.json",
            "runs/residual_production_checkpoint_work_order_current.json",
            "runs/residual_production_training_data_contract_current.json",
            "runs/residual_force_gpu_worker_return_receipt_current.json",
            "runs/residual_force_derivation_validation_current.json",
            "runs/residual_force_gpu_worker_handoff_package_current.json",
            "runs/product_production_ai_gpu_return_intake_current.json",
            "runs/rocm_environment_manifest_current.json",
            "runs/residual_production_output_head_gap_contract_current.json",
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
        "artifact_id": "production_ai_registry_promotion_operator_field_worksheet",
        "artifact_path": "runs/production_ai_registry_promotion_operator_field_worksheet_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_field_worksheet.py",
        "depends_on": [
            "tools/product/build_production_ai_registry_promotion_operator_field_worksheet.py",
            "tools/accounting/build_production_ai_registry_promotion_operator_field_worksheet.py",
            "tools/build_production_ai_registry_promotion_operator_field_worksheet.py",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
        ],
    },
    {
        "artifact_id": "production_ai_registry_promotion_operator_staging_apply",
        "artifact_path": "runs/production_ai_registry_promotion_operator_staging_apply_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_staging_apply.py",
        "depends_on": [
            "tools/product/build_production_ai_registry_promotion_operator_staging_apply.py",
            "tools/accounting/build_production_ai_registry_promotion_operator_staging_apply.py",
            "tools/build_production_ai_registry_promotion_operator_staging_apply.py",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_operator_field_worksheet_current.json",
            "runs/residual_model_registry_current.json",
            "runs/product_production_ai_checkpoint_readiness_current.json",
        ],
    },
    {
        "artifact_id": "product_scope_breadth_contract",
        "artifact_path": "runs/product_scope_breadth_contract_current.json",
        "builder_command": "python3 tools/build_product_scope_breadth_contract.py",
        "depends_on": [
            "tools/accounting/build_product_scope_breadth_contract.py",
            "tools/build_product_scope_breadth_contract.py",
        ],
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
        "artifact_id": "product_scope_breadth_evidence_operator_field_worksheet",
        "artifact_path": "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
        "builder_command": (
            "python3 tools/build_product_scope_breadth_evidence_operator_field_worksheet.py"
        ),
        "depends_on": [
            "tools/product/build_product_scope_breadth_evidence_operator_field_worksheet.py",
            "tools/accounting/build_product_scope_breadth_evidence_operator_field_worksheet.py",
            "tools/build_product_scope_breadth_evidence_operator_field_worksheet.py",
            "config/product_scope_breadth_evidence_receipt_current.csv",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/product_scope_breadth_evidence_priority_packet_current.json",
            "runs/product_scope_breadth_closure_checklist_current.json",
        ],
    },
    {
        "artifact_id": "product_scope_breadth_evidence_operator_staging_apply",
        "artifact_path": "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
        "builder_command": (
            "python3 tools/build_product_scope_breadth_evidence_operator_staging_apply.py"
        ),
        "depends_on": [
            "tools/product/build_product_scope_breadth_evidence_operator_staging_apply.py",
            "tools/accounting/build_product_scope_breadth_evidence_operator_staging_apply.py",
            "tools/build_product_scope_breadth_evidence_operator_staging_apply.py",
            "config/product_scope_breadth_evidence_receipt_current.csv",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
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
        "artifact_id": "product_quality_gate_verification",
        "artifact_path": "runs/product_quality_gate_verification_current.json",
        "builder_command": (
            "python3 scripts/verify_quality_gate.py --quiet --out-json "
            "runs/product_quality_gate_verification_current.json"
        ),
        "depends_on": [
            "scripts/verify_quality_gate.py",
            "betelgeuze_product/operational_quality.py",
            "betelgeuze_product/docking_request.py",
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
        "artifact_id": "api_runner_profile_promotion_operator_staging_apply",
        "artifact_path": "runs/api_runner_profile_promotion_operator_staging_apply_current.json",
        "builder_command": "python3 tools/build_api_runner_profile_promotion_operator_staging_apply.py",
        "depends_on": [
            "tools/product/build_api_runner_profile_promotion_operator_staging_apply.py",
            "tools/accounting/build_api_runner_profile_promotion_operator_staging_apply.py",
            "tools/build_api_runner_profile_promotion_operator_staging_apply.py",
            "runs/api_runner_profile_promotion_readiness_current.json",
            "runs/api_runner_profile_promotion_operator_receipt_current.json",
            "runs/api_runner_profile_promotion_operator_template_current.csv",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/science_claim_promotion_gap_closure_current.json",
        ],
    },
    {
        "artifact_id": "tier_alpha_adrb2_dispatch_smoke",
        "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
        "builder_command": "python3 tools/product/run_tier_alpha_adrb2_dispatch_smoke.py --timeout-seconds 420",
        "depends_on": [
            "tools/product/run_tier_alpha_adrb2_dispatch_smoke.py",
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
        "artifact_id": "architecture_validation_package_report",
        "artifact_path": "runs/architecture_validation_package_report_current.json",
        "builder_command": "python3 tools/build_architecture_validation_package_report.py",
        "depends_on": [
            "tools/product/build_architecture_validation_package_report.py",
            "tools/build_architecture_validation_package_report.py",
            "docs/architecture_validation_test_packages.md",
            "runs/product_gpcr_adrb2_after_approval_summary.json",
            "runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json",
            "runs/external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_kinase_core_full_p0_n1000000_r1_stage5_ranking_summary.json",
            "runs/product_public_benchmark_contract_current.json",
            "runs/public_benchmark_residual_assist_comparison_gate_current.json",
            "runs/residual_energy_force_label_validation_current.json",
            "runs/residual_shadow_ab_current.json",
            "runs/api_docking_dispatch_e2e_evidence_current.json",
            "runs/local_delivery_verdict_gate_current.json",
            "runs/local_delivery/bundle_product_gpcr_adrb2/validation.json",
            "runs/architecture_validation_public_benchmark_subset_manifests_current.json",
            "runs/architecture_validation_speedpack_ab_retrospective_current.json",
            "runs/biorxiv_external_validation_audit_current.json",
            "runs/competition_benchmark_rollup_current.json",
            "casp17/casp17_historical_winner_normalized_bands_current.json",
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
            "runs/architecture_validation_package_report_current.json",
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
        "artifact_id": "ai_md_contract_source_of_truth_gate",
        "artifact_path": "runs/ai_md_contract_source_of_truth_gate_current.json",
        "builder_command": "python3 tools/product/build_ai_md_contract_source_of_truth_gate.py",
        "depends_on": [
            "tools/product/build_ai_md_contract_source_of_truth_gate.py",
            "pyproject.toml",
            "api/job_store.py",
            "api/main.py",
            "api/models.py",
            "api/validated_runner.py",
            "api/worker.py",
            "betelgeuze_ai_md/__init__.py",
            "betelgeuze_ai_md/contracts/__init__.py",
            "betelgeuze_ai_md/contracts/api_adapter.py",
            "betelgeuze_ai_md/contracts/backmapping_adapter.py",
            "betelgeuze_ai_md/contracts/interaction_adapter.py",
            "betelgeuze_ai_md/contracts/topology_adapter.py",
            "betelgeuze_ai_md/contracts/claim_scope.py",
            "betelgeuze_ai_md/contracts/input_schema.py",
            "betelgeuze_ai_md/contracts/output_schema.py",
            "betelgeuze_ai_md/contracts/verdict_schema.py",
            "betelgeuze_ai_md/contracts/manifest.py",
            "betelgeuze_ai_md/contracts/serialization.py",
            "betelgeuze_ai_md/coarse_md/__init__.py",
            "betelgeuze_ai_md/coarse_md/numpy_ref.py",
            "tools/product/validate_api_runner_profiles.py",
            "tests/unit/test_betelgeuze_ai_md_contracts.py",
            "tests/unit/test_betelgeuze_ai_md_api_adapter.py",
            "tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py",
            "tests/unit/test_betelgeuze_ai_md_topology_adapter.py",
            "tests/unit/test_betelgeuze_ai_md_numpy_ref.py",
            "tests/unit/test_api_validated_runner_adapter.py",
            "tests/unit/test_api_job_store.py",
            "tests/unit/test_build_ai_md_contract_source_of_truth_gate.py",
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
            "api/main.py",
            "api/product.py",
            "api/product_ai_surface.py",
            "api/product_architecture.py",
            "api/product_benchmark.py",
            "api/product_capabilities.py",
            "api/product_cameo_runner.py",
            "api/product_commercial_readiness.py",
            "api/product_docking.py",
            "api/product_evidence_goal.py",
            "api/product_gpcr_hard_decoy.py",
            "api/product_hbond_backmap.py",
            "api/product_license.py",
            "api/product_operational.py",
            "api/product_pocketmd_lite.py",
            "api/product_production_ai.py",
            "api/product_release_evidence.py",
            "api/product_release_ops.py",
            "api/product_scope.py",
            "api/product_service_contracts.py",
            "api/product_tier_beta.py",
            "pyproject.toml",
        ],
    },
    {
        "artifact_id": "product_public_benchmark_scorecard_intake_sync",
        "artifact_path": "runs/product_public_benchmark_scorecard_intake_sync_current.json",
        "builder_command": PRODUCT_PUBLIC_BENCHMARK_SCORECARD_INTAKE_SYNC_COMMAND,
        "depends_on": [
            "tools/sync_product_public_benchmark_scorecard_intake.py",
            "runs/lit_pcba_scorecard_row_current.csv",
            "runs/dude_z_decoy_smoke_scorecard_row_current.csv",
            "runs/pdbbind_casf_pose_affinity_scorecard_row_current.csv",
            "runs/protein_protein_docking_benchmark_v5_scorecard_row_current.csv",
            "runs/casp_archive_structure_regression_scorecard_row_current.csv",
        ],
    },
    {
        "artifact_id": "product_public_benchmark_contract",
        "artifact_path": "runs/product_public_benchmark_contract_current.json",
        "builder_command": PRODUCT_PUBLIC_BENCHMARK_CONTRACT_COMMAND,
        "depends_on": [
            "tools/accounting/build_product_public_benchmark_contract.py",
            "tools/build_product_public_benchmark_contract.py",
            "betelgeuze_product/public_benchmark.py",
            "runs/product_public_benchmark_scorecard_intake.csv",
            "runs/product_public_benchmark_scorecard_intake_sync_current.json",
            "runs/lit_pcba_scorecard_current.json",
            "runs/dude_z_decoy_smoke_scorecard_current.json",
            "runs/pdbbind_casf_pose_affinity_scorecard_current.json",
            "runs/protein_protein_docking_benchmark_v5_scorecard_current.json",
            "runs/casp_archive_structure_regression_scorecard_current.json",
            "runs/lit_pcba_materialization_manifest_current.json",
            "runs/dude_z_decoy_smoke_materialization_manifest_current.json",
            "runs/pdbbind_casf_pose_affinity_materialization_manifest_current.json",
            "runs/protein_protein_docking_benchmark_v5_materialization_manifest_current.json",
            "runs/casp_archive_structure_regression_materialization_manifest_current.json",
            "runs/pdbbind_casf_pose_affinity_results_current.json",
        ],
    },
    {
        "artifact_id": "product_public_benchmark_work_order",
        "artifact_path": "runs/product_public_benchmark_work_order_current.json",
        "builder_command": PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_COMMAND,
        "depends_on": [
            "tools/accounting/build_product_public_benchmark_work_order.py",
            "tools/build_product_public_benchmark_work_order.py",
            "betelgeuze_product/public_benchmark_work_order.py",
            "runs/product_public_benchmark_contract_current.json",
        ],
    },
    {
        "artifact_id": "public_benchmark_phase2_harness_audit",
        "artifact_path": "runs/public_benchmark_phase2_harness_audit_current.json",
        "builder_command": PUBLIC_BENCHMARK_PHASE2_HARNESS_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_public_benchmark_phase2_harness_audit.py",
            "betelgeuze_product/public_benchmark.py",
            "runs/product_public_benchmark_contract_current.json",
        ],
    },
    {
        "artifact_id": "benchmark_ledger",
        "artifact_path": "runs/benchmark_ledger_current.json",
        "builder_command": BENCHMARK_LEDGER_COMMAND,
        "depends_on": [
            "tools/product/build_benchmark_ledger.py",
            "betelgeuze_product/benchmark_ledger.py",
        ],
    },
    {
        "artifact_id": "public_benchmark_vina_gnina_comparison_work_order",
        "artifact_path": "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
        "builder_command": PUBLIC_BENCHMARK_VINA_GNINA_COMPARISON_WORK_ORDER_COMMAND,
        "depends_on": [
            "tools/product/build_public_benchmark_vina_gnina_comparison_work_order.py",
            "tools/accounting/build_pdbbind_casf_pose_affinity_results.py",
            "docs/docking_comparison_contract.md",
            "runs/pdbbind_casf_pose_affinity_results_current.json",
            "runs/pdbbind_casf_pose_affinity_fixed_gold_metadata_current.csv",
        ],
    },
    {
        "artifact_id": "public_benchmark_vina_gnina_score_template_receipt",
        "artifact_path": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
        "builder_command": PUBLIC_BENCHMARK_VINA_GNINA_SCORE_TEMPLATE_RECEIPT_COMMAND,
        "depends_on": [
            "tools/product/build_public_benchmark_vina_gnina_score_template_receipt.py",
            "tools/product/build_public_benchmark_vina_gnina_comparison_work_order.py",
            "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
            "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_current_fit_closure_probe",
        "artifact_path": "runs/gpcr_hard_decoy_current_fit_closure_probe_current.json",
        "builder_command": GPCR_HARD_DECOY_CURRENT_FIT_CLOSURE_PROBE_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_current_fit_closure_probe.py",
            "runs/gpcr_coverage_v2_supervised_logreg_l2_c10_shadow_replay_scores_current.csv",
            (
                "runs/external_validation_2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1_"
                "set1_core_blind_gpcr_core_full_hard_decoy_labels_balanced.csv"
            ),
            (
                "runs/external_validation_2026-05-17_gpcr_a1_coverage_v2_beta_rescue_fast_r1_"
                "set1_core_blind_gpcr_core_full_hard_decoy_split.csv"
            ),
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_adora2a_neutral_rescue_probe",
        "artifact_path": "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_current.json",
        "builder_command": GPCR_HARD_DECOY_ADORA2A_NEUTRAL_RESCUE_PROBE_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_adora2a_neutral_rescue_probe.py",
            "tools/product/build_gpcr_hard_decoy_current_fit_closure_probe.py",
            "runs/gpcr_hard_decoy_current_fit_closure_probe_current.json",
            "runs/gpcr_hard_decoy_current_fit_closure_probe_scores_current.csv",
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_adora2a_preregistered_replay",
        "artifact_path": "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json",
        "builder_command": GPCR_HARD_DECOY_ADORA2A_PREREGISTERED_REPLAY_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_adora2a_preregistered_replay.py",
            "tools/product/build_gpcr_hard_decoy_current_fit_closure_probe.py",
            "tools/product/build_gpcr_hard_decoy_adora2a_neutral_rescue_probe.py",
            "tools/accounting/build_gpcr_residual_prototype_spec.py",
            "tools/run_ligand_backmapping_scoring.py",
            "runs/gpcr_hard_decoy_current_fit_closure_probe_scores_current.csv",
            "runs/gpcr_hard_decoy_adora2a_neutral_rescue_probe_scores_current.csv",
            "runs/gpcr_residual_prototype_spec_adora2a_neutral_antagonist_rescue_v1_current.json",
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_suite_current_input",
        "artifact_path": "runs/gpcr_hard_decoy_suite_current_input_provenance.json",
        "builder_command": GPCR_HARD_DECOY_SUITE_CURRENT_INPUT_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_suite_current_input.py",
            "tools/product/build_gpcr_hard_decoy_suite_report.py",
            "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json",
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_suite_report",
        "artifact_path": "runs/gpcr_hard_decoy_suite_current.json",
        "builder_command": GPCR_HARD_DECOY_SUITE_REPORT_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_suite_report.py",
            "betelgeuze_product/gpcr_hard_decoy_suite.py",
            "config/gpcr_hard_decoy_suite_current.csv",
            "runs/gpcr_hard_decoy_suite_current_input_provenance.json",
        ],
    },
    {
        "artifact_id": "gpcr_a1_independent_repeat_packet",
        "artifact_path": "runs/gpcr_a1_independent_repeat_packet_current.json",
        "builder_command": GPCR_A1_INDEPENDENT_REPEAT_PACKET_COMMAND,
        "depends_on": [
            "tools/accounting/build_gpcr_a1_independent_repeat_packet.py",
            "tools/build_gpcr_a1_independent_repeat_packet.py",
            "runs/gpcr_a1_accuracy_repair_queue_current.json",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json",
            (
                "runs/gpcr_scaleup_100k_family_balanced_coverage_v1_candidate_current/specs/"
                "gpcr_core_family_balanced_rescore_100k_coverage-v1-family-balanced100k.json"
            ),
        ],
    },
    {
        "artifact_id": "gpcr_hard_decoy_claim_unlock_audit",
        "artifact_path": "runs/gpcr_hard_decoy_claim_unlock_audit_current.json",
        "builder_command": GPCR_HARD_DECOY_CLAIM_UNLOCK_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_gpcr_hard_decoy_claim_unlock_audit.py",
            "tools/gpcr_replay/build_gpcr_active_scorer_promotion_decision_packet.py",
            "runs/gpcr_hard_decoy_suite_current.json",
            "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json",
            "runs/gpcr_a1_independent_repeat_packet_current.json",
            "runs/accuracy_parity_scorecard_current.json",
            # Promotion context artifacts are independently freshness-gated below. Making this
            # metric-closure packet depend on them creates a release-refresh cycle through the
            # capability surface and active-scorer promotion packets.
        ],
    },
    {
        "artifact_id": "pocketmd_lite_stage3_contact_clash_intake",
        "artifact_path": "runs/pocketmd_lite_stage3_contact_clash_intake_current.json",
        "builder_command": POCKETMD_LITE_STAGE3_CONTACT_CLASH_INTAKE_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py",
            "config/pocketmd_lite_candidates_current.csv",
            "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage3_summary.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_report",
        "artifact_path": "runs/pocketmd_lite_report_current.json",
        "builder_command": POCKETMD_LITE_REPORT_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_report.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "config/pocketmd_lite_candidates_current.csv",
            "runs/pocketmd_lite_stage3_contact_clash_intake_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_refinement_work_order",
        "artifact_path": "runs/pocketmd_lite_refinement_work_order_current.json",
        "builder_command": POCKETMD_LITE_REFINEMENT_WORK_ORDER_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_refinement_work_order.py",
            "runs/pocketmd_lite_report_current.json",
            "config/pocketmd_lite_candidates_current.csv",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_remaining_evidence_queue",
        "artifact_path": "runs/pocketmd_lite_remaining_evidence_queue_current.json",
        "builder_command": POCKETMD_LITE_REMAINING_EVIDENCE_QUEUE_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_remaining_evidence_queue.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "runs/pocketmd_lite_report_current.json",
            "config/pocketmd_lite_candidates_current.csv",
            "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage3_summary.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_evidence_recovery_manifest",
        "artifact_path": "runs/pocketmd_lite_evidence_recovery_manifest_current.json",
        "builder_command": POCKETMD_LITE_EVIDENCE_RECOVERY_MANIFEST_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_evidence_recovery_manifest.py",
            "runs/pocketmd_lite_remaining_evidence_queue_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_metric_collection_input_pack",
        "artifact_path": "runs/pocketmd_lite_metric_collection_input_pack_current.json",
        "builder_command": POCKETMD_LITE_METRIC_COLLECTION_INPUT_PACK_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_metric_collection_input_pack.py",
            "runs/pocketmd_lite_remaining_evidence_queue_current.json",
            "runs/pocketmd_lite_evidence_recovery_manifest_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_ligand_atom_frame_recovery",
        "artifact_path": "runs/pocketmd_lite_ligand_atom_frame_recovery_current.json",
        "builder_command": POCKETMD_LITE_LIGAND_ATOM_FRAME_RECOVERY_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_ligand_atom_frame_recovery.py",
            "runs/pocketmd_lite_metric_collection_input_pack_current.csv",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_bounded_metric_collector",
        "artifact_path": "runs/pocketmd_lite_bounded_metric_collector_current.json",
        "builder_command": POCKETMD_LITE_BOUNDED_METRIC_COLLECTOR_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_bounded_metric_collector.py",
            "tools/gpcr_replay/build_gpcr_drd2_local_minimization_survival.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "runs/pocketmd_lite_metric_collection_input_pack_current.csv",
            "runs/pocketmd_lite_ligand_atom_frame_recovery_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_metric_collection_probe",
        "artifact_path": "runs/pocketmd_lite_metric_collection_probe_current.json",
        "builder_command": POCKETMD_LITE_METRIC_COLLECTION_PROBE_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_metric_collection_probe.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "runs/pocketmd_lite_metric_collection_input_pack_current.csv",
            "runs/pocketmd_lite_bounded_metric_collector_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_claim_grade_metric_source_audit",
        "artifact_path": "runs/pocketmd_lite_claim_grade_metric_source_audit_current.json",
        "builder_command": POCKETMD_LITE_CLAIM_GRADE_METRIC_SOURCE_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_claim_grade_metric_source_audit.py",
            "runs/pocketmd_lite_metric_collection_input_pack_current.csv",
            "runs/pocketmd_lite_metric_collection_probe_current.json",
            "runs/pocketmd_lite_ligand_atom_frame_recovery_current.json",
            "runs/pocketmd_lite_bounded_metric_collector_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_candidate_metric_fill_preview",
        "artifact_path": "runs/pocketmd_lite_candidate_metric_fill_preview_current.json",
        "builder_command": POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_candidate_metric_fill_preview.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "config/pocketmd_lite_candidates_current.csv",
            "runs/pocketmd_lite_metric_collection_probe_current.json",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_candidate_metric_fill_preview_report",
        "artifact_path": "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json",
        "builder_command": POCKETMD_LITE_CANDIDATE_METRIC_FILL_PREVIEW_REPORT_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_report.py",
            "betelgeuze_product/pocketmd_lite_contract.py",
            "runs/pocketmd_lite_candidate_metric_fill_preview_current.json",
            "runs/pocketmd_lite_candidate_metric_fill_preview_current.candidates.csv",
        ],
    },
    {
        "artifact_id": "pocketmd_lite_topk_refinement_audit",
        "artifact_path": "runs/pocketmd_lite_topk_refinement_audit_current.json",
        "builder_command": POCKETMD_LITE_TOPK_REFINEMENT_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_pocketmd_lite_topk_refinement_audit.py",
            "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json",
            "runs/pocketmd_lite_metric_collection_probe_current.json",
            "runs/pocketmd_lite_remaining_evidence_queue_current.json",
            "runs/pocketmd_lite_candidate_metric_fill_preview_current.json",
            "runs/pocketmd_lite_claim_grade_metric_source_audit_current.json",
        ],
    },
    {
        "artifact_id": "hbond_backmap_report",
        "artifact_path": "runs/hbond_backmap_report_current.json",
        "builder_command": HBOND_BACKMAP_REPORT_COMMAND,
        "depends_on": [
            "tools/product/build_hbond_backmap_report.py",
            "betelgeuze_product/hbond_backmap_report.py",
            "betelgeuze_product/structured_reason.py",
            "docs/hbond_backmap_contract.md",
            "runs/product_image_smoke_runner_artifacts/backmapping_scores.csv",
        ],
    },
    {
        "artifact_id": "product_capability_surface_contract",
        "artifact_path": "runs/product_capability_surface_contract_current.json",
        "builder_command": "python3 tools/build_product_capability_surface_contract.py",
        "depends_on": [
            "tools/accounting/build_product_capability_surface_contract.py",
            "tools/build_product_capability_surface_contract.py",
            "betelgeuze_product/capability_surface.py",
            "betelgeuze_product/docking_request.py",
            "runs/restricted_unattended_execution_readiness_current.json",
            "runs/product_security_deployment_contract_current.json",
            "runs/gpcr_hard_decoy_suite_current.json",
            "runs/pocketmd_lite_report_current.json",
            "runs/pocketmd_lite_remaining_evidence_queue_current.json",
            "runs/pocketmd_lite_candidate_metric_fill_preview_report_current.json",
            "runs/pocketmd_lite_topk_refinement_audit_current.json",
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
        "artifact_id": "gpcr_commercial_phase_ab_closure_chain",
        "artifact_path": "runs/gpcr_commercial_phase_ab_closure_chain_current.json",
        "builder_command": "python3 tools/build_gpcr_commercial_phase_ab_closure_chain.py",
        "depends_on": [
            "tools/gpcr_replay/build_gpcr_commercial_phase_ab_closure_chain.py",
            "tools/build_gpcr_commercial_phase_ab_closure_chain.py",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/gpcr_guarded_operational_gate_refresh_chain_current.json",
            "runs/gpcr_frozen_ranking_quality_repair_chain_current.json",
            "runs/product_operational_quality_contract_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/product_delivery_evidence_contract_current.json",
            "runs/product_pilot_packet_contract_current.json",
            "runs/product_capability_surface_contract_current.json",
            "runs/product_commercial_independence_gate_current.json",
        ],
    },
    {
        "artifact_id": "gpcr_active_scorer_promotion_decision_packet",
        "artifact_path": "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
        "builder_command": "python3 tools/build_gpcr_active_scorer_promotion_decision_packet.py",
        "depends_on": [
            "tools/gpcr_replay/build_gpcr_active_scorer_promotion_decision_packet.py",
            "tools/build_gpcr_active_scorer_promotion_decision_packet.py",
            "runs/gpcr_commercial_phase_ab_closure_chain_current.json",
            "runs/gpcr_guarded_operational_gate_refresh_chain_current.json",
            "runs/gpcr_a1_independent_repeat_packet_current.json",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/product_execution_approval_gate_current.json",
            "runs/product_bundle_contract_current.json",
            "runs/product_delivery_evidence_contract_current.json",
            "runs/residual_model_registry_current.json",
        ],
    },
    {
        "artifact_id": "gpcr_broad_claim_scope_readiness",
        "artifact_path": "runs/gpcr_broad_claim_scope_readiness_current.json",
        "builder_command": "python3 tools/build_gpcr_broad_claim_scope_readiness.py",
        "depends_on": [
            "tools/gpcr_replay/build_gpcr_broad_claim_scope_readiness.py",
            "tools/accounting/build_gpcr_broad_claim_scope_readiness.py",
            "tools/build_gpcr_broad_claim_scope_readiness.py",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/gpcr_family_heldout_scorecard_guardrail_current.json",
            "runs/gpcr_guarded_100k_rerun_readiness_current.json",
            "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
            "runs/gpcr_broad_claim_review_receipt_current.json",
        ],
    },
    {
        "artifact_id": "gpcr_broad_claim_review_receipt",
        "artifact_path": "runs/gpcr_broad_claim_review_receipt_current.json",
        "builder_command": "python3 tools/build_gpcr_broad_claim_review_receipt.py",
        "depends_on": [
            "tools/gpcr_replay/build_gpcr_broad_claim_review_receipt.py",
            "tools/accounting/build_gpcr_broad_claim_review_receipt.py",
            "tools/build_gpcr_broad_claim_review_receipt.py",
            "config/gpcr_broad_claim_review_receipt_current.csv",
            "runs/gpcr_family_heldout_scorecard_guardrail_current.json",
            "runs/gpcr_guarded_100k_rerun_readiness_current.json",
            "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
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
            "scripts/check_independent_product_readiness.py",
            "scripts/verify_quality_gate.py",
            "runs/product_quality_gate_verification_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "runs/production_ai_registry_promotion_operator_staging_apply_current.json",
            "runs/api_runner_profile_promotion_operator_receipt_current.json",
            "runs/product_pose_sampling_readiness_current.json",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
            "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
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
        "artifact_id": "product_image_smoke_preflight",
        "artifact_path": "runs/product_image_smoke_preflight_current.json",
        "builder_command": "python3 tools/build_product_image_smoke_preflight.py",
        "depends_on": [
            "tools/product/build_product_image_smoke_preflight.py",
            "tools/build_product_image_smoke_preflight.py",
            "deploy/verify_product_image.sh",
            ".github/workflows/product-image-smoke.yml",
            "Dockerfile.product",
            "requirements-base.txt",
            "requirements-rocm.txt",
            "requirements-product-rocm.txt",
            "runs/product_image_smoke_receipt_current.json",
        ],
    },
    {
        "artifact_id": "ai_md_product_evidence_bundle",
        "artifact_path": "runs/ai_md_product_evidence_bundle_current.json",
        "builder_command": "python3 tools/build_ai_md_product_evidence_bundle.py",
        "depends_on": [
            "tools/product/build_ai_md_product_evidence_bundle.py",
            "tools/product/build_ai_md_engine_kpi_report.py",
            "tools/product/build_product_image_smoke_preflight.py",
            "tools/build_ai_md_product_evidence_bundle.py",
            "tools/build_ai_md_engine_kpi_report.py",
            "tools/build_product_image_smoke_preflight.py",
            "runs/ai_md_engine_kpi_report_current.json",
            "runs/rocm_environment_manifest_current.json",
            "runs/product_image_smoke_preflight_current.json",
            "Dockerfile.product",
            "requirements-base.txt",
            "requirements-rocm.txt",
            "requirements-product-rocm.txt",
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
            "runs/product_release_bundle_current.json",
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
        "artifact_id": "developer_preview_final_gate_audit",
        "artifact_path": "runs/developer_preview_final_gate_audit_current.json",
        "builder_command": DEVELOPER_PREVIEW_FINAL_GATE_AUDIT_COMMAND,
        "depends_on": [
            "tools/build_backmapping_scoring_batch_smoke_benchmark.py",
            "tools/build_ligand_scaleup_benchmark_summary.py",
            "tools/build_product_end_to_end_rocm_benchmark.py",
            "tools/build_product_execution_preflight.py",
            "tools/build_product_execution_work_order.py",
            "tools/build_product_pose_sampling_readiness.py",
            "tools/product/build_backmapping_scoring_batch_smoke_benchmark.py",
            "tools/product/build_developer_preview_large_model_oom_guard_receipt.py",
            "tools/product/build_developer_preview_final_gate_audit.py",
            "tools/product/build_developer_preview_new_user_observation_receipt.py",
            "tools/product/build_developer_preview_platform_reproducibility_receipt.py",
            "tools/product/build_developer_preview_silent_import_loss_receipt.py",
            "tools/product/build_ligand_scaleup_benchmark_summary.py",
            "tools/product/build_product_end_to_end_rocm_benchmark.py",
            "tools/product/build_product_pose_sampling_readiness.py",
            "docs/developer_preview_final_gate_action_register.md",
        ],
    },
    {
        "artifact_id": "goal_readiness_rollup",
        "artifact_path": "runs/goal_readiness_rollup_current.json",
        "builder_command": "python3 tools/build_goal_readiness_rollup.py",
        "depends_on": [
            "tools/accounting/build_goal_readiness_rollup.py",
            "tools/build_goal_readiness_rollup.py",
            "betelgeuze_product/cli.py",
            "betelgeuze_cameo/cli.py",
            "betelgeuze_cleanup/cli.py",
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
            "runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_current.csv",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_metric_source_materialization",
        "artifact_path": "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_METRIC_MATERIALIZATION_COMMAND,
        "depends_on": [
            "tools/product/materialize_refine_tier_public_benchmark_metric_sources.py",
            "tools/product/build_refine_tier_public_benchmark_readiness.py",
            "tools/accounting/build_pdbbind_casf_pose_affinity_results.py",
            "core/mm_gbsa.py",
            "core/score_calibration.py",
            "core/structure_metrics.py",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
            "runs/refine_tier_public_benchmark_science_input_gap_current.csv",
            "runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_work_order_apply_materialized",
        "artifact_path": "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_COMMAND,
        "depends_on": [
            "tools/product/apply_refine_tier_public_benchmark_work_order.py",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_materialized_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv",
            "runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv",
            "runs/refine_tier_public_benchmark_metric_sources",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_work_order",
        "artifact_path": "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_COMMAND,
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_work_order.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_work_order.py",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_candidate_queue",
        "artifact_path": "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_CANDIDATE_QUEUE_COMMAND,
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_candidate_queue.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_candidate_queue.py",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
            "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv",
            "data/public_benchmarks/pdbbind_casf_pose_affinity/pdb_to_affinity.txt.original",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_intake",
        "artifact_path": "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_COMMAND,
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_intake.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_coordinate_intake.py",
            "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json"
        ),
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_PLAN_COMMAND,
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json"
        ),
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_APPLY_COMMAND,
        "depends_on": [
            "tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py",
            "tools/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py",
            "tools/product/fetch_public_benchmark_native_structure.py",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_COMMAND
        ),
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight.py",
            "tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py",
            "tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_templates.py",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_COMMAND
        ),
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt.py",
            "config/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.csv",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json",
        ],
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_COMMAND
        ),
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness.py",
            "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_validation_current.csv",
        ],
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_source_templates"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_COMMAND
        ),
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_templates.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_metric_source_templates.py",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
        ],
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_COMMAND
        ),
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py",
            "tools/build_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt.py",
            "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
        ],
    },
    {
        "artifact_id": "refine_tier_public_benchmark_claim_grade_gap_audit",
        "artifact_path": "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_refine_tier_public_benchmark_claim_grade_gap_audit.py",
            "tools/build_refine_tier_public_benchmark_claim_grade_gap_audit.py",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json",
            "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json",
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
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_materialized_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json",
            "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json",
        ],
    },
    {
        "artifact_id": "public_benchmark_external_receipts_audit",
        "artifact_path": "runs/public_benchmark_external_receipts_audit_current.json",
        "builder_command": PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_COMMAND,
        "depends_on": [
            "tools/product/build_public_benchmark_external_receipts_audit.py",
            "runs/pdbbind_casf_pose_affinity_materialization_manifest_current.json",
            "runs/pdbbind_casf_pose_affinity_results_current.json",
            "runs/public_benchmark_phase2_harness_audit_current.json",
            "runs/pdbbind_casf_pose_affinity_result_provenance_current.json",
            "runs/pdbbind_casf_pose_affinity_scorecard_current.json",
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV,
            "runs/benchmark_ledger_current.json",
            "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
            "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
        ],
    },
    {
        "artifact_id": "public_benchmark_receipt_attach_packet",
        "artifact_path": "runs/public_benchmark_receipt_attach_packet_current.json",
        "builder_command": PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_COMMAND,
        "depends_on": [
            "tools/product/build_public_benchmark_receipt_attach_packet.py",
            "runs/public_benchmark_external_receipts_audit_current.json",
            "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
            "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
            "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV,
        ],
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_operator_field_worksheet",
        "artifact_path": "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
        "builder_command": (
            "python3 tools/build_engine_refinement_claim_evidence_operator_field_worksheet.py"
        ),
        "depends_on": [
            "tools/product/build_engine_refinement_claim_evidence_operator_field_worksheet.py",
            "tools/accounting/build_engine_refinement_claim_evidence_operator_field_worksheet.py",
            "tools/build_engine_refinement_claim_evidence_operator_field_worksheet.py",
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
            "runs/refine_tier_public_benchmark_readiness_current.json",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_current.json",
            "runs/refine_tier_public_benchmark_receptor_coordinate_intake_current.csv",
            "runs/refine_tier_public_benchmark_receptor_coordinate_validation_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_current.csv",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_materialized_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
            R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON,
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json",
        ],
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_operator_staging_apply",
        "artifact_path": "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
        "builder_command": (
            "python3 tools/build_engine_refinement_claim_evidence_operator_staging_apply.py"
        ),
        "depends_on": [
            "tools/product/build_engine_refinement_claim_evidence_operator_staging_apply.py",
            "tools/accounting/build_engine_refinement_claim_evidence_operator_staging_apply.py",
            "tools/build_engine_refinement_claim_evidence_operator_staging_apply.py",
            "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
            "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
            "runs/refine_tier_public_benchmark_work_order_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_current.json",
            "runs/engine_refinement_claim_promotion_action_board_current.csv",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_materialized_current.csv",
            "runs/refine_tier_public_benchmark_metric_evidence_materialized_current.csv",
            "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
        ],
    },
    {
        "artifact_id": "science_accuracy_frontier",
        "artifact_path": "runs/science_accuracy_frontier_current.json",
        "builder_command": "python3 tools/product/build_science_accuracy_frontier.py",
        "depends_on": [
            "tools/product/build_science_accuracy_frontier.py",
            "runs/accuracy_parity_scorecard_current.json",
            "runs/gpcr_broad_claim_scope_readiness_current.json",
            "runs/engine_refinement_tier_readiness_current.json",
            "runs/refine_tier_public_benchmark_readiness_current.json",
            "runs/refine_tier_public_benchmark_metric_source_materialization_current.json",
            "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json",
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json",
            "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json",
            "config/refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup_current.json",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
            "runs/product_pose_sampling_readiness_current.json",
        ],
    },
    {
        "artifact_id": "product_goal_completion_audit",
        "artifact_path": "runs/product_goal_completion_audit_current.json",
        "builder_command": "python3 tools/build_product_goal_completion_audit.py",
        "depends_on": [
            "tools/accounting/build_product_goal_completion_audit.py",
            "tools/build_product_goal_completion_audit.py",
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
            "tools/accounting/build_goal_operator_action_board.py",
            "tools/build_goal_operator_action_board.py",
            "runs/goal_readiness_rollup_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/engine_refinement_claim_promotion_action_board_current.csv",
        ],
    },
    {
        "artifact_id": "product_operator_cockpit",
        "artifact_path": "runs/product_operator_cockpit_current.json",
        "builder_command": PRODUCT_OPERATOR_COCKPIT_COMMAND,
        "depends_on": [
            "tools/product/build_product_operator_cockpit.py",
            "api/main.py",
            "api/product.py",
            "api/product_operator_cockpit.py",
            "runs/product_capability_surface_contract_current.json",
            "runs/goal_readiness_rollup_current.json",
            "runs/hbond_backmap_report_current.json",
            "runs/gpcr_hard_decoy_claim_unlock_audit_current.json",
            "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.json",
            "runs/pocketmd_lite_topk_refinement_audit_current.json",
            "runs/public_benchmark_external_receipts_audit_current.json",
            "runs/public_benchmark_receipt_attach_packet_current.json",
            "runs/goal_release_decision_gate_current.json",
            "runs/goal_operator_action_board_current.json",
            "runs/ai_md_product_evidence_bundle_current.json",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/customer_shadow_evidence_status_current.json",
            "runs/enterprise_on_prem_readiness_gate_current.json",
        ],
    },
    {
        "artifact_id": "support_bundle",
        "artifact_path": "runs/support_bundle_current.json",
        "builder_command": SUPPORT_BUNDLE_COMMAND,
        "depends_on": [
            "tools/product/build_support_bundle.py",
            "runs/product_security_deployment_contract_current.json",
            "runs/product_job_orchestration_contract_current.json",
            "runs/product_rollout_execution_smoke_receipt_current.json",
            "runs/product_ledger_privacy_scan_current.json",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/self_hosted_license_distribution_audit_current.json",
        ],
    },
    {
        "artifact_id": "enterprise_on_prem_readiness_gate",
        "artifact_path": "runs/enterprise_on_prem_readiness_gate_current.json",
        "builder_command": ENTERPRISE_ON_PREM_READINESS_GATE_COMMAND,
        "depends_on": [
            "tools/product/build_enterprise_on_prem_readiness_gate.py",
            "runs/product_service_boundary_contract_current.json",
            "runs/product_security_deployment_contract_current.json",
            "runs/product_job_orchestration_contract_current.json",
            "runs/product_rollout_execution_readiness_current.json",
            "runs/product_rollout_execution_smoke_receipt_current.json",
            "runs/self_hosted_license_distribution_audit_current.json",
            "runs/product_ledger_privacy_scan_current.json",
            "runs/api_customer_flow_release_evidence_current.json",
            "runs/support_bundle_current.json",
            "docs/product_stage_and_roadmap_2026_06_30.md",
            "docs/target_bioscience_architecture.md",
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
            "runs/product_scope_breadth_evidence_priority_packet_current.json",
            "runs/product_scope_breadth_evidence_receipt_current.json",
            "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
            "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
            "config/product_scope_breadth_evidence_receipt_current.csv",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
            "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
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
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
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
            "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
            "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
            "runs/engine_refinement_claim_evidence_receipt_current.json",
            "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
            "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
            "runs/product_goal_completion_audit_current.json",
            "runs/goal_bottleneck_briefing_current.json",
        ],
    },
    {
        "artifact_id": "aqp1_direct_binding_external_evidence_operator_fill_guide",
        "artifact_path": "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
        "builder_command": (
            "python3 tools/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py"
        ),
        "depends_on": [
            "tools/product/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py",
            "tools/build_aqp1_direct_binding_external_evidence_operator_fill_guide.py",
            "runs/aqp1_direct_binding_procurement_packet_current.json",
            "runs/aqp1_operator_validation_candidate_packet_current.json",
            "runs/aqp1_functional_kcal_surrogate_packet_current.json",
        ],
    },
    {
        "artifact_id": "aqp1_direct_binding_external_evidence_operator_worksheet",
        "artifact_path": "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
        "builder_command": (
            "python3 tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py"
        ),
        "depends_on": [
            "tools/product/build_aqp1_direct_binding_external_evidence_operator_worksheet.py",
            "tools/build_aqp1_direct_binding_external_evidence_operator_worksheet.py",
            "tools/product/build_aqp1_direct_binding_external_evidence_intake.py",
            "tools/build_aqp1_direct_binding_external_evidence_intake.py",
            "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
            "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv",
            "runs/aqp1_direct_binding_procurement_packet_current.json",
            "runs/aqp1_operator_validation_candidate_packet_current.json",
            "runs/aqp1_functional_kcal_surrogate_packet_current.json",
        ],
    },
    {
        "artifact_id": "aqp1_direct_binding_external_evidence_operator_staging_apply",
        "artifact_path": "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
        "builder_command": (
            "python3 tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py "
            "--mode preview --staging-csv runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
        ),
        "depends_on": [
            "tools/product/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py",
            "tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py",
            "tools/product/build_aqp1_direct_binding_external_evidence_intake.py",
            "tools/build_aqp1_direct_binding_external_evidence_intake.py",
            "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
            "runs/aqp1_direct_binding_external_evidence_intake_supplement_example_current.csv",
            "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv",
            "runs/aqp1_direct_binding_procurement_packet_current.json",
            "runs/aqp1_operator_validation_candidate_packet_current.json",
            "runs/aqp1_functional_kcal_surrogate_packet_current.json",
        ],
    },
    {
        "artifact_id": "aqp1_negative_evidence_intake_gate",
        "artifact_path": "runs/aqp1_negative_evidence_intake_gate_current.json",
        "builder_command": "python3 tools/build_aqp1_negative_evidence_intake_gate.py",
        "depends_on": [
            "tools/accounting/build_aqp1_negative_evidence_intake_gate.py",
            "tools/build_aqp1_negative_evidence_intake_gate.py",
            "runs/aqp1_negative_evidence_request_packet_current.json",
            "runs/aqp1_negative_evidence_intake_current.csv",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_operator_packet",
        "artifact_path": "runs/product_commercial_readiness_operator_packet_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_operator_packet.py",
        "depends_on": [
            "tools/accounting/build_product_commercial_readiness_operator_packet.py",
            "tools/build_product_commercial_readiness_operator_packet.py",
            "runs/product_goal_completion_audit_current.json",
            "runs/aqp1_direct_binding_procurement_packet_current.json",
            "runs/aqp1_direct_binding_external_evidence_operator_fill_guide_current.json",
            "runs/aqp1_direct_binding_external_evidence_operator_worksheet_current.json",
            "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
            "runs/production_ai_registry_promotion_operator_receipt_current.json",
            "runs/production_ai_registry_promotion_priority_packet_current.json",
            "runs/production_ai_registry_promotion_operator_field_worksheet_current.json",
            "runs/production_ai_registry_promotion_operator_staging_apply_current.json",
            "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
            "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
            "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
            "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
            "config/production_ai_registry_promotion_operator_receipt_current.csv",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_handoff_bundle",
        "artifact_path": "runs/product_commercial_readiness_handoff_bundle_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
        "depends_on": [
            "tools/product/build_product_commercial_readiness_handoff_bundle.py",
            "tools/accounting/build_product_commercial_readiness_handoff_bundle.py",
            "tools/build_product_commercial_readiness_handoff_bundle.py",
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
            "tools/product/build_product_commercial_readiness_operator_packet_freshness.py",
            "tools/accounting/build_product_commercial_readiness_operator_packet_freshness.py",
            "tools/build_product_commercial_readiness_operator_packet_freshness.py",
            "runs/product_goal_completion_audit_current.json",
            "runs/product_commercial_readiness_operator_packet_current.json",
        ],
    },
    {
        "artifact_id": "product_commercial_readiness_execution_ladder",
        "artifact_path": "runs/product_commercial_readiness_execution_ladder_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_execution_ladder.py",
        "depends_on": [
            "tools/product/build_product_commercial_readiness_execution_ladder.py",
            "tools/accounting/build_product_commercial_readiness_execution_ladder.py",
            "tools/build_product_commercial_readiness_execution_ladder.py",
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
            "runs/product_scope_breadth_evidence_priority_packet_current.json",
            "runs/engine_refinement_claim_evidence_priority_packet_current.json",
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
        "artifact_id": "ai_md_contract_source_of_truth_gate_semantic_ready",
        "artifact_path": "runs/ai_md_contract_source_of_truth_gate_current.json",
        "builder_command": "python3 tools/product/build_ai_md_contract_source_of_truth_gate.py",
        "required_status": "ai_md_contract_source_of_truth_gate_ready",
        "required_true_fields": [
            "ai_md_contract_source_of_truth_gate_ready",
            "contract_source_files_ready",
            "ai_md_contract_layer_ready",
            "ai_residual_contract_ready",
            "api_evidence_bundle_attachment_ready",
            "api_runtime_evidence_bundle_surface_ready",
            "numpy_reference_oracle_ready",
            "trajectory_summary_contract_ready",
            "evidence_bundle_trajectory_claim_ready",
            "evidence_bundle_backmapped_pose_claim_ready",
            "evidence_bundle_interaction_claim_ready",
            "evidence_bundle_product_output_claim_ready",
            "evidence_bundle_ai_uncertainty_claim_ready",
            "claim_widening_guard_ready",
            "topology_validity_contract_ready",
            "topology_factory_adapter_ready",
            "backmapping_interaction_adapter_ready",
        ],
        "required_int_exact_fields": {
            "blocker_count": 0,
            "missing_source_file_count": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "docking_results_emitted": 0,
            "full_commercial_claim_allowed": 0,
        },
    },
    {
        "artifact_id": "product_image_smoke_preflight_semantic_ready",
        "artifact_path": "runs/product_image_smoke_preflight_current.json",
        "builder_command": "python3 tools/build_product_image_smoke_preflight.py",
        "required_status": "product_image_smoke_preflight_ready",
        "required_true_fields": [
            "script_contract_ready",
            "workflow_contract_ready",
            "clean_container_smoke_ready",
            "container_runtime_receipt_ready",
            "container_runtime_in_container",
            "container_runtime_device_nodes_ready",
            "container_runtime_torch_rocm_ready",
            "container_runtime_torch_cuda_available",
            "container_runtime_rust_hip_backend_enabled",
            "product_runner_smoke_ready",
        ],
        "required_int_exact_fields": {
            "receipt_simulate_missing_profile_http": 422,
        },
        "required_int_min_fields": {
            "container_runtime_visible_device_count": 1,
        },
        "required_text_exact_fields": {
            "container_runtime_proof_schema_version": "rocm_container_runtime_proof_v1",
            "receipt_mode": "rocm-runtime",
            "receipt_status": "product_image_smoke_ready",
        },
    },
    {
        "artifact_id": "ai_md_product_evidence_bundle_semantic_ready",
        "artifact_path": "runs/ai_md_product_evidence_bundle_current.json",
        "builder_command": "python3 tools/build_ai_md_product_evidence_bundle.py",
        "required_status": "ai_md_product_evidence_bundle_ready",
        "required_true_fields": [
            "bundle_export_ready",
            "rocm_hip_rust_runtime_ready",
            "product_image_preflight_ready",
            "source_artifacts_fresh",
        ],
        "required_int_exact_fields": {
            "required_artifact_missing_count": 0,
            "bundle_validation_error_count": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "benchmark_executed": 0,
            "product_claim_ready": 1,
            "release_claim_ready": 0,
        },
        "required_text_exact_fields": {
            "product_image_receipt_mode": "rocm-runtime",
            "release_claim_blocked_reason": "product_ci_runtime_gate_not_ready",
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
            "customer_report_evidence_binding_ready",
            "customer_report_delivery_contract_ready",
            "evidence_traceability_ready",
            "production_ai_abstention_enforced",
            "scope_claim_guard_ready",
            "scope_claim_limit_ready",
            "shadow_abstention_ready",
            "structured_customer_report_ready",
        ],
        "required_int_exact_fields": {
            "general_platform_claim_allowed": 0,
            "production_ai_correction_applied": 0,
            "model_inference_executed": 0,
            "docking_results_emitted": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "required_section_count": 7,
            "section_count": 7,
            "ready_section_count": 7,
            "blocked_section_count": 0,
        },
        "required_text_exact_fields": {
            "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
            "uncertainty_policy_mode": "shadow_abstention",
        },
    },
    {
        "artifact_id": "product_ai_report_ux_contract_semantic_ready",
        "artifact_path": "runs/product_ai_report_ux_contract_current.json",
        "builder_command": "python3 tools/build_product_ai_report_ux_contract.py",
        "required_status": "product_ai_report_ux_contract_ready",
        "required_true_fields": [
            "ai_report_ux_ready",
            "customer_report_card_ready",
            "customer_report_delivery_contract_ready",
            "customer_report_evidence_binding_ready",
            "customer_report_viewer_binding_ready",
            "evidence_traceability_ready",
            "scope_claim_guard_ready",
            "scope_claim_limit_ready",
            "shadow_abstention_ready",
            "structured_customer_report_ready",
            "viewer_customer_report_binding_ready",
            "viewer_interaction_surface_ready",
            "viewer_ready",
        ],
        "required_int_exact_fields": {
            "general_platform_claim_allowed": 0,
            "model_inference_executed": 0,
            "docking_results_emitted": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "customer_report_required_block_count": 7,
            "customer_report_ready_block_count": 7,
            "customer_report_blocked_block_count": 0,
            "ready_section_count": 10,
            "blocked_section_count": 0,
        },
        "required_text_exact_fields": {
            "primary_abstention_reason": "production_residual_checkpoint_not_promoted",
            "uncertainty_policy_mode": "shadow_abstention",
        },
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
        "artifact_id": "product_quality_gate_verification_semantic_ready",
        "artifact_path": "runs/product_quality_gate_verification_current.json",
        "builder_command": (
            "python3 scripts/verify_quality_gate.py --quiet --out-json "
            "runs/product_quality_gate_verification_current.json"
        ),
        "required_status": "product_quality_gate_verified",
        "required_true_fields": [
            "quality_gate_ready",
        ],
        "required_int_exact_fields": {
            "check_count": 4,
            "pass_count": 4,
            "blocker_count": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "source_contract_status": "product_operational_quality_contract_ready",
        },
    },
    {
        "artifact_id": "product_release_bundle_semantic_ready",
        "artifact_path": "runs/product_release_bundle_current.json",
        "builder_command": "python3 deploy/product_release_bundle.py",
        "required_status": "release_bundle_ready_for_operator_review",
        "required_true_fields": [
            "release_bundle_ready",
        ],
        "required_int_exact_fields": {
            "artifact_count": 32,
            "check_count": 24,
            "pass_count": 24,
            "blocker_count": 0,
        },
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
        "artifact_id": "gpcr_commercial_phase_ab_closure_chain_claim_locked_metric_ready",
        "artifact_path": "runs/gpcr_commercial_phase_ab_closure_chain_current.json",
        "builder_command": "python3 tools/build_gpcr_commercial_phase_ab_closure_chain.py",
        "required_status": "blocked_gpcr_commercial_phase_ab_closure_claim_locked",
        "required_true_fields": [
            "accuracy_parity_metric_ready",
            "accuracy_parity_claim_scope_lock_only",
        ],
        "required_int_exact_fields": {
            "claim_promotion_allowed": 0,
            "scorer_apply_allowed": 0,
        },
        "required_text_exact_fields": {
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
        },
    },
    {
        "artifact_id": "gpcr_active_scorer_promotion_decision_claim_locked_metric_ready",
        "artifact_path": "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
        "builder_command": "python3 tools/build_gpcr_active_scorer_promotion_decision_packet.py",
        "required_status": "blocked_gpcr_active_scorer_promotion_decision",
        "required_true_fields": [
            "accuracy_parity_metric_ready",
            "accuracy_parity_claim_scope_lock_only",
            "delivery_ready_claim_allowed",
            "product_execution_authorized",
        ],
        "required_int_exact_fields": {
            "active_scorer_apply_allowed": 0,
            "scorer_apply_allowed": 0,
            "claim_promotion_allowed": 0,
            "router_claim_allowed": 0,
            "platform_claim_allowed": 0,
            "residual_production_promotion_allowed": 0,
            "blocker_count": 3,
        },
        "required_text_exact_fields": {
            "promotion_scope": "guarded_operational_gpcr_ranking_only",
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
        },
    },
    {
        "artifact_id": "gpcr_broad_claim_review_receipt_blocked_semantic_ready",
        "artifact_path": "runs/gpcr_broad_claim_review_receipt_current.json",
        "builder_command": "python3 tools/build_gpcr_broad_claim_review_receipt.py",
        "required_status": "blocked_gpcr_broad_claim_review_receipt",
        "required_true_fields": [
            "receipt_csv_present",
        ],
        "required_int_exact_fields": {
            "broad_claim_review_receipt_ready": 0,
            "target_heldout_broad_scope_review_approved": 0,
            "scorer_router_promotion_gate_approved": 0,
            "receipt_row_count": 2,
            "required_review_count": 2,
            "pass_row_count": 0,
            "blocked_row_count": 2,
            "operator_review_surface_ready_count": 2,
            "operator_review_surface_blocked_count": 0,
            "evidence_artifact_present_count": 0,
            "evidence_status_contract_present_count": 2,
            "expected_true_fields_present_count": 2,
            "external_engine_calls_zero_count": 2,
            "receipt_manual_field_pending_count": 16,
            "missing_required_review_count": 0,
            "duplicate_review_id_count": 0,
            "missing_required_column_count": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_GPCR_BROAD_CLAIM_REVIEW",
            "first_blocked_review_id": "target_heldout_broad_scope_review_not_approved",
            "first_blocked_expected_evidence_status": "gpcr_target_heldout_broad_claim_review_ready",
        },
    },
    {
        "artifact_id": "gpcr_broad_claim_scope_readiness_target_heldout_ready_claim_locked",
        "artifact_path": "runs/gpcr_broad_claim_scope_readiness_current.json",
        "builder_command": "python3 tools/build_gpcr_broad_claim_scope_readiness.py",
        "required_status": "blocked_gpcr_broad_claim_scope_readiness",
        "required_true_fields": [
            "target_heldout_family_guardrail_ready",
            "guarded_100k_claim_review_inputs_ready",
            "target_heldout_broad_scope_review_input_ready",
            "formal_broad_claim_review_blocked",
            "scorer_router_promotion_gate_blocked",
            "accuracy_parity_metric_ready",
            "accuracy_parity_claim_scope_lock_only",
            "active_scorer_decision_recorded",
        ],
        "required_int_exact_fields": {
            "target_heldout_broad_scope_review_approved": 0,
            "broad_claim_review_receipt_ready": 0,
            "broad_claim_review_receipt_row_count": 2,
            "broad_claim_review_receipt_pass_row_count": 0,
            "broad_claim_review_receipt_blocked_row_count": 2,
            "broad_claim_review_receipt_operator_review_surface_ready_count": 2,
            "broad_claim_review_receipt_operator_review_surface_blocked_count": 0,
            "broad_claim_review_receipt_evidence_artifact_present_count": 0,
            "broad_claim_review_receipt_evidence_status_contract_present_count": 2,
            "broad_claim_review_receipt_expected_true_fields_present_count": 2,
            "broad_claim_review_receipt_external_engine_calls_zero_count": 2,
            "broad_claim_review_receipt_manual_field_pending_count": 16,
            "active_scorer_gate_ready": 0,
            "scorer_router_promotion_gate_receipt_approved": 0,
            "scorer_router_promotion_gate_ready": 0,
            "claim_promotion_allowed": 0,
            "router_claim_allowed": 0,
            "platform_claim_allowed": 0,
            "blocker_count": 2,
        },
        "required_text_exact_fields": {
            "promotion_scope": "guarded_operational_gpcr_ranking_only",
            "accuracy_parity_ligand_ranking_status": "restricted_pass",
            "heldout_guardrail_status": "green",
            "guarded_100k_readiness_status": "eligible",
            "broad_claim_review_receipt_status": "blocked_gpcr_broad_claim_review_receipt",
            "broad_claim_review_receipt_first_blocked_review_id": (
                "target_heldout_broad_scope_review_not_approved"
            ),
            "broad_claim_review_receipt_approval_token_required": "APPROVE_GPCR_BROAD_CLAIM_REVIEW",
        },
    },
    {
        "artifact_id": "product_goal_completion_audit_full_commercial_release_blockers_semantic_ready",
        "artifact_path": "runs/product_goal_completion_audit_current.json",
        "builder_command": "python3 tools/build_product_goal_completion_audit.py",
        "required_status": "blocked_product_goal_completion_audit",
        "required_true_fields": [],
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
            "profile_count": 5,
            "receipt_row_count": 5,
            "pass_row_count": 0,
            "blocked_row_count": 5,
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
        "artifact_id": "api_runner_profile_promotion_operator_staging_apply_blocked_semantic_ready",
        "artifact_path": "runs/api_runner_profile_promotion_operator_staging_apply_current.json",
        "builder_command": "python3 tools/build_api_runner_profile_promotion_operator_staging_apply.py",
        "required_status": "blocked_api_runner_profile_promotion_operator_staging_apply",
        "required_true_fields": [
            "staging_operator_template_csv_present",
            "live_operator_template_csv_present",
            "accuracy_parity_present",
            "science_claim_present",
        ],
        "required_int_exact_fields": {
            "staging_row_count": 5,
            "staging_missing_required_column_count": 0,
            "staging_placeholder_row_count": 0,
            "live_operator_template_row_count": 5,
            "candidate_operator_template_written": 0,
            "candidate_operator_receipt_ready": 0,
            "candidate_profile_count": 5,
            "candidate_pass_row_count": 0,
            "candidate_blocked_row_count": 5,
            "candidate_blocker_count": 1,
            "candidate_approved_profile_count": 0,
            "candidate_promote_decision_count": 0,
            "candidate_keep_enabled_decision_count": 0,
            "accuracy_parity_gate_ready": 0,
            "overall_commercial_tool_accuracy_parity_allowed": 0,
            "schrodinger_class_claim_allowed": 0,
            "science_claim_gate_ready": 0,
            "science_claim_promotion_allowed": 0,
            "science_claim_open_gap_count": 0,
            "broad_promotion_gate_required": 0,
            "broad_promotion_gate_ready": 0,
            "broad_commercial_profile_promotion_allowed": 0,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "live_copy_allowed": 0,
            "write_canonical_operator_template_requested": 0,
            "canonical_operator_template_written": 0,
            "profile_json_edited_by_this_tool": 0,
            "profile_enabled_by_this_tool": 0,
            "runner_executed": 0,
            "docking_results_emitted": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "mode": "preview",
            "staging_operator_template_csv": "runs/api_runner_profile_promotion_operator_template_current.csv",
            "live_operator_template_csv": "runs/api_runner_profile_promotion_operator_template_current.csv",
            "candidate_operator_template_csv": "runs/api_runner_profile_promotion_operator_receipt_candidate_current.csv",
            "candidate_operator_receipt_status": "blocked_api_runner_profile_promotion_operator_receipt",
            "candidate_first_blocked_profile_id": "backmapping_scoring.example",
            "candidate_first_blocked_row_blocker": "operator_decision_missing",
            "candidate_most_common_row_blocker": "operator_decision_missing",
            "accuracy_parity_status": "blocked_accuracy_parity",
            "science_claim_status": "science_claim_promotion_gap_closure_complete",
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
            "checkpoint_preflight_ready",
            "production_output_heads_complete",
            "production_inference_acceptance_matrix_ready",
        ],
        "required_int_exact_fields": {
            "production_ai_checkpoint_ready": 0,
            "production_ai_inference_subject_active": 0,
            "production_promotion_allowed": 0,
            "trained_model_checkpoint_count": 1,
            "force_gpu_worker_return_receipt_ready": 1,
            "selected_sidecar_ready": 1,
            "production_training_data_ready": 1,
            "registry_promotion_upstream_acceptance_ready": 1,
            "production_inference_acceptance_blocked_stage_count": 1,
        },
        "required_text_exact_fields": {
            "default_residual_mode": "shadow",
            "production_inference_actionable_blocker_stage_id": "registry_guarded_promotion_acceptance",
            "production_inference_actionable_blocker_check_id": "registry_customer_facing_promotion_allowed",
            "production_inference_actionable_blocker_artifact": "runs/residual_model_registry_current.json",
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
            "trained_model_checkpoint_count": 1,
            "registry_promotion_upstream_acceptance_ready": 1,
            "post_return_promotion_ladder_blocked_stage_count": 3,
        },
        "required_text_exact_fields": {
            "default_residual_mode": "shadow",
            "first_blocked_stage_id": "residual_model_registry",
            "first_blocked_stage_artifact": "runs/residual_model_registry_current.json",
            "first_blocked_stage_ready_key": "production_promotion_allowed",
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
            "observed_registry_trained_model_checkpoint_count": 1,
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
            "operator_input_required_count": 3,
            "blocked_priority_item_count": 3,
            "required_gate_count": 4,
            "registry_promotion_missing_gate_count": 3,
            "observed_registry_trained_model_checkpoint_count": 1,
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
            "top_gate_id": "default_residual_mode_guarded",
            "top_priority_bucket": "guarded_residual_mode_selection_required",
            "top_acceptance_artifact": "runs/residual_model_registry_current.json",
            "observed_registry_default_residual_mode": "shadow",
        },
    },
    {
        "artifact_id": "production_ai_registry_promotion_operator_field_worksheet_semantic_ready",
        "artifact_path": "runs/production_ai_registry_promotion_operator_field_worksheet_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_field_worksheet.py",
        "required_status": "production_ai_registry_promotion_operator_field_worksheet_ready",
        "required_true_fields": [
            "field_worksheet_ready",
            "receipt_csv_present",
            "operator_receipt_artifact_present",
            "registry_artifact_present",
            "checkpoint_readiness_artifact_present",
            "priority_packet_artifact_present",
        ],
        "required_int_exact_fields": {
            "operator_fill_complete": 0,
            "receipt_row_count": 1,
            "worksheet_field_row_count": 20,
            "required_receipt_field_count": 19,
            "operator_fill_pending_field_count": 13,
            "invalid_field_count": 0,
            "diagnostic_required_field_count": 6,
            "diagnostic_required_pending_field_count": 6,
            "observed_registry_trained_model_checkpoint_count": 1,
            "observed_registry_production_promotion_allowed": 0,
            "observed_registry_customer_facing_mutation_flags_ready": 0,
            "observed_checkpoint_registry_promotion_currently_satisfied": 0,
            "model_promoted": 0,
            "customer_facing_mutation_enabled": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "operator_receipt_status": "blocked_production_ai_registry_promotion_operator_receipt",
            "priority_packet_status": "blocked_production_ai_registry_promotion_priority_packet",
            "top_gate_id": "default_residual_mode_guarded",
            "top_priority_bucket": "guarded_residual_mode_selection_required",
            "approval_token_required": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "observed_registry_default_residual_mode": "shadow",
        },
    },
    {
        "artifact_id": "production_ai_registry_promotion_operator_staging_apply_blocked_semantic_ready",
        "artifact_path": "runs/production_ai_registry_promotion_operator_staging_apply_current.json",
        "builder_command": "python3 tools/build_production_ai_registry_promotion_operator_staging_apply.py",
        "required_status": "blocked_production_ai_registry_promotion_operator_staging_apply",
        "required_true_fields": [
            "staging_csv_present",
            "live_receipt_csv_present",
            "field_worksheet_present",
        ],
        "required_int_exact_fields": {
            "staging_row_count": 1,
            "staging_missing_required_column_count": 0,
            "staging_placeholder_row_count": 1,
            "live_receipt_row_count": 1,
            "candidate_receipt_written": 0,
            "candidate_receipt_ready": 0,
            "candidate_pass_row_count": 0,
            "candidate_blocked_row_count": 1,
            "candidate_blocker_count": 1,
            "candidate_observed_registry_trained_model_checkpoint_count": 1,
            "candidate_observed_registry_production_promotion_allowed": 0,
            "candidate_observed_checkpoint_registry_promotion_currently_satisfied": 0,
            "field_worksheet_pending_field_count": 13,
            "field_worksheet_diagnostic_required_pending_field_count": 6,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "live_copy_allowed": 0,
            "write_canonical_receipt_requested": 0,
            "canonical_receipt_written": 0,
            "registry_edited_by_this_tool": 0,
            "checkpoint_created_by_this_tool": 0,
            "model_promoted": 0,
            "customer_facing_mutation_enabled": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "mode": "preview",
            "staging_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "live_receipt_csv": "config/production_ai_registry_promotion_operator_receipt_current.csv",
            "candidate_receipt_csv": "runs/production_ai_registry_promotion_operator_receipt_candidate_current.csv",
            "candidate_receipt_status": "blocked_production_ai_registry_promotion_operator_receipt",
            "candidate_first_blocked_artifact_id": "residual_model_registry_guarded_promotion",
            "candidate_first_blocked_row_blocker": "operator_placeholders_unfilled",
            "candidate_most_common_row_blocker": "operator_placeholders_unfilled",
            "candidate_observed_registry_default_residual_mode": "shadow",
            "field_worksheet_status": "production_ai_registry_promotion_operator_field_worksheet_ready",
            "field_worksheet_top_gate_id": "default_residual_mode_guarded",
            "field_worksheet_top_priority_bucket": "guarded_residual_mode_selection_required",
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
            "evidence_status_contract_present_count": 6,
            "evidence_status_verified_count": 0,
            "expected_true_fields_present_count": 6,
            "expected_quality_true_field_count": 4,
            "expected_int_min_field_count": 4,
            "expected_false_field_count": 4,
            "provenance_kind_accepted_count": 6,
            "external_state_mutated_false_count": 6,
            "operator_attestation_accepted_count": 6,
            "operator_review_surface_ready_count": 6,
            "operator_review_surface_blocked_count": 0,
            "receipt_manual_field_pending_count": 36,
            "receipt_evidence_artifact_pending_count": 6,
            "receipt_claim_ready_pending_count": 6,
            "receipt_reviewer_pending_count": 6,
            "receipt_reviewed_at_utc_pending_count": 6,
            "receipt_license_ok_pending_count": 6,
            "receipt_approval_token_pending_count": 6,
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
        "artifact_id": "product_scope_breadth_evidence_operator_field_worksheet_semantic_ready",
        "artifact_path": "runs/product_scope_breadth_evidence_operator_field_worksheet_current.json",
        "builder_command": (
            "python3 tools/build_product_scope_breadth_evidence_operator_field_worksheet.py"
        ),
        "required_status": "product_scope_breadth_evidence_operator_field_worksheet_ready",
        "required_true_fields": [
            "field_worksheet_ready",
            "receipt_csv_present",
            "receipt_artifact_present",
            "priority_packet_artifact_present",
            "scope_checklist_artifact_present",
            "priority_packet_ready",
        ],
        "required_int_exact_fields": {
            "operator_fill_complete": 0,
            "receipt_row_count": 6,
            "receipt_field_row_count": 72,
            "required_receipt_field_count": 66,
            "operator_fill_pending_field_count": 36,
            "invalid_field_count": 0,
            "top_blocker_field_count": 12,
            "top_blocker_pending_field_count": 6,
            "priority_open_item_count": 15,
            "priority_scientific_evidence_request_count": 11,
            "priority_local_crosscheck_candidate_count": 11,
            "priority_review_only_keep_blocked_count": 1,
            "scope_checklist_blocker_class_count": 6,
            "scope_checklist_manual_review_subcheck_count": 39,
            "scope_checklist_ready_for_apply_count": 0,
            "claim_promotion_allowed": 0,
            "claim_promoted": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "receipt_status": "blocked_product_scope_breadth_evidence_receipt",
            "priority_packet_status": "product_scope_breadth_evidence_priority_packet_ready",
            "top_blocker_id": "direct_binding_evidence_missing",
            "top_item_id": "AQP1.core_binder_01",
            "top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
            "top_required_evidence_type": "exact_transporter_target_pair_quantitative_binder_kcal",
            "top_review_template_artifact": "runs/transporter_manual_review_intake_template_current.json",
            "top_apply_gate_artifact": "runs/transporter_binder_promotion_gate_current.json",
            "approval_token_required": "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT",
        },
    },
    {
        "artifact_id": "product_scope_breadth_evidence_operator_staging_apply_blocked_semantic_ready",
        "artifact_path": "runs/product_scope_breadth_evidence_operator_staging_apply_current.json",
        "builder_command": (
            "python3 tools/build_product_scope_breadth_evidence_operator_staging_apply.py"
        ),
        "required_status": "blocked_product_scope_breadth_evidence_operator_staging_apply",
        "required_true_fields": [
            "staging_csv_present",
            "live_receipt_csv_present",
            "field_worksheet_present",
        ],
        "required_int_exact_fields": {
            "staging_row_count": 6,
            "staging_missing_required_column_count": 0,
            "staging_placeholder_row_count": 6,
            "live_receipt_row_count": 6,
            "candidate_receipt_written": 0,
            "candidate_receipt_ready": 0,
            "candidate_pass_row_count": 0,
            "candidate_blocked_row_count": 6,
            "candidate_blocker_count": 1,
            "candidate_evidence_artifact_present_count": 0,
            "candidate_evidence_status_verified_count": 0,
            "field_worksheet_pending_field_count": 36,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "live_copy_allowed": 0,
            "write_canonical_receipt_requested": 0,
            "canonical_receipt_written": 0,
            "claim_promotion_allowed": 0,
            "claim_promoted": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "mode": "preview",
            "staging_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "live_receipt_csv": "config/product_scope_breadth_evidence_receipt_current.csv",
            "candidate_receipt_csv": "runs/product_scope_breadth_evidence_receipt_candidate_current.csv",
            "candidate_receipt_status": "blocked_product_scope_breadth_evidence_receipt",
            "candidate_first_blocked_scope_blocker_id": "direct_binding_evidence_missing",
            "candidate_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "candidate_first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "candidate_first_blocked_observed_evidence_status": "missing",
            "candidate_most_common_row_blocker": "operator_placeholders_unfilled",
            "field_worksheet_status": "product_scope_breadth_evidence_operator_field_worksheet_ready",
            "field_worksheet_top_blocker_id": "direct_binding_evidence_missing",
            "field_worksheet_top_item_id": "AQP1.core_binder_01",
            "field_worksheet_top_bucket": "local_crosscheck_review_present_but_exact_quant_required",
        },
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_candidate_queue_semantic_ready",
        "artifact_path": "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_CANDIDATE_QUEUE_COMMAND,
        "required_status": "refine_tier_public_benchmark_statistical_support_candidate_queue_ready",
        "required_true_fields": [
            "candidate_queue_ready",
            "statistical_support_work_order_present",
            "statistical_support_work_order_ready",
            "current_work_order_csv_present",
            "seed_csv_present",
            "experimental_deltaG_source_present",
        ],
        "required_int_exact_fields": {
            "current_work_order_row_count": 8,
            "existing_target_exclusion_count": 8,
            "seed_csv_source_row_count": 16,
            "seed_source_row_count": 22492,
            "local_pose_inventory_pose_row_count": 22492,
            "local_pose_inventory_ligand_reference_row_count": 285,
            "candidate_source_eligible_row_count": 17,
            "candidate_source_excluded_existing_target_row_count": 8,
            "candidate_source_distinct_target_count": 17,
            "candidate_fill_recovery_candidate_count": 17,
            "candidate_fill_recovery_payload_write_allowed": 0,
            "candidate_fill_recovery_claim_promotion_allowed": 0,
            "expansion_slot_count": 17,
            "selected_candidate_count": 17,
            "holdout_selected_candidate_count": 5,
            "fit_or_holdout_selected_candidate_count": 12,
            "ligand_pose_artifact_present_count": 17,
            "receptor_coordinate_artifact_present_count": 17,
            "receptor_coordinate_artifact_missing_count": 0,
            "experimental_deltaG_prefilled_count": 17,
            "candidate_ready_for_metric_materialization_count": 17,
            "candidate_ready_for_canonical_intake_count": 0,
            "canonical_intake_promotion_allowed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "candidate_source_mode": "candidate_fill_recovery",
            "statistical_support_work_order": (
                "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json"
            ),
            "current_work_order_csv": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "seed_csv": "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv",
            "experimental_deltaG_source": (
                "data/public_benchmarks/pdbbind_casf_pose_affinity/pdb_to_affinity.txt.original"
            ),
            "next_required_step": (
                "Review and place public receptor/complex coordinate artifacts for the selected 17 "
                "candidates, then materialize DockQ, lDDT-PLI, and internal DeltaG source payloads "
                "before canonical intake or claim receipt promotion."
            ),
        },
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_intake_semantic_ready",
        "artifact_path": "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_COMMAND,
        "required_status": "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready",
        "required_true_fields": [
            "coordinate_intake_ready",
            "candidate_queue_present",
            "candidate_queue_ready",
        ],
        "required_int_exact_fields": {
            "candidate_queue_selected_candidate_count": 17,
            "coordinate_intake_row_count": 17,
            "coordinate_intake_artifact_present_row_count": 17,
            "coordinate_intake_missing_row_count": 0,
            "coordinate_intake_suggested_public_url_row_count": 17,
            "coordinate_intake_suggested_local_path_row_count": 17,
            "coordinate_intake_suggested_local_path_candidate_count": 136,
            "coordinate_intake_suggested_local_path_present_count": 17,
            "coordinate_intake_suggested_local_path_present_target_count": 17,
            "coordinate_intake_suggested_local_path_missing_target_count": 0,
            "coordinate_intake_expected_archive_member_example_count": 51,
            "coordinate_intake_operator_review_required_row_count": 17,
            "coordinate_validation_row_count": 17,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "coordinate_validation_missing_row_count": 0,
            "coordinate_validation_below_min_atom_row_count": 0,
            "coordinate_validation_below_min_macromolecule_row_count": 0,
            "coordinate_validation_below_min_protein_like_row_count": 0,
            "coordinate_validation_min_atom_records": 20,
            "coordinate_validation_min_macromolecule_atom_records": 20,
            "coordinate_validation_min_distinct_residues": 5,
            "coordinate_validation_min_protein_like_residues": 5,
            "ligand_pose_artifact_present_count": 17,
            "experimental_deltaG_prefilled_count": 17,
            "candidate_ready_for_metric_materialization_count": 17,
            "candidate_ready_for_canonical_intake_count": 0,
            "canonical_intake_promotion_allowed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "candidate_queue": (
                "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json"
            ),
            "next_required_step": (
                "Place and review receptor/complex coordinate artifacts for the 17 selected "
                "statistical-support candidates, then rerun coordinate validation before metric "
                "source materialization or claim receipt promotion."
            ),
        },
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_semantic_ready",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json"
        ),
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_PLAN_COMMAND,
        "required_status": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready",
        "required_true_fields": [
            "coordinate_fetch_plan_ready",
            "coordinate_intake_present",
            "coordinate_intake_ready",
        ],
        "required_int_exact_fields": {
            "coordinate_intake_row_count": 17,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "coordinate_fetch_row_count": 17,
            "coordinate_fetch_required_row_count": 0,
            "coordinate_fetch_blocked_row_count": 0,
            "coordinate_fetch_primary_url_row_count": 17,
            "coordinate_fetch_staging_destination_row_count": 17,
            "coordinate_fetch_destination_present_row_count": 17,
            "coordinate_fetch_current_artifact_present_row_count": 17,
            "coordinate_fetch_ready_for_validation_row_count": 17,
            "coordinate_fetch_operator_review_required_row_count": 17,
            "coordinate_fetch_external_download_executed": 0,
            "canonical_intake_promotion_allowed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "coordinate_intake": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json"
            ),
            "next_required_step": (
                "Run an operator-approved public coordinate fetch/staging step for the 17 R9 "
                "statistical-support targets, then rerun coordinate intake validation before metric "
                "source materialization."
            ),
        },
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_blocked_semantic_ready"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json"
        ),
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_APPLY_COMMAND,
        "required_status": (
            "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply"
        ),
        "required_true_fields": [
            "coordinate_fetch_apply_preview_ready",
            "coordinate_fetch_plan_present",
            "coordinate_fetch_plan_ready",
            "post_fetch_validation_supported",
        ],
        "required_int_exact_fields": {
            "coordinate_fetch_apply_live_ready": 0,
            "execution_requested": 0,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "coordinate_fetch_apply_row_count": 17,
            "coordinate_fetch_apply_preflight_pass_row_count": 17,
            "coordinate_fetch_apply_preview_ready_row_count": 17,
            "coordinate_fetch_apply_blocked_row_count": 0,
            "coordinate_fetch_apply_downloaded_row_count": 0,
            "coordinate_fetch_apply_destination_present_after_row_count": 17,
            "coordinate_fetch_apply_ready_for_validation_row_count": 17,
            "post_fetch_validation_requested": 0,
            "post_fetch_validation_executed": 0,
            "post_fetch_validation_coordinate_intake_ready": 0,
            "post_fetch_validation_coordinate_validation_row_count": 0,
            "post_fetch_validation_coordinate_validation_pass_row_count": 0,
            "post_fetch_validation_coordinate_validation_blocked_row_count": 0,
            "post_fetch_validation_coordinate_validation_missing_row_count": 0,
            "post_fetch_validation_candidate_ready_for_metric_materialization_count": 0,
            "download_executed": 0,
            "canonical_intake_promotion_allowed": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "coordinate_fetch_plan": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json"
            ),
            "mode": "preview",
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
            "post_fetch_validation_candidate_queue": (
                "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json"
            ),
            "post_fetch_validation_json": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json"
            ),
            "post_fetch_validation_intake_csv": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.csv"
            ),
            "post_fetch_validation_validation_csv": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_validation_current.csv"
            ),
            "post_fetch_validation_md": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.md"
            ),
            "next_required_step": (
                "Set APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD as the approval token and "
                "rerun with --mode execute, then rebuild coordinate intake validation."
            ),
        },
    },
    {
        "artifact_id": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_semantic_ready",
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_COMMAND
        ),
        "required_status": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
        ),
        "required_true_fields": [
            "r4_preflight_ready",
            "operator_approval_required",
            "operator_confirmation_required",
            "fetch_plan_present",
            "fetch_plan_ready",
            "fetch_apply_present",
            "fetch_apply_preview_ready",
            "post_fetch_validation_supported",
            "metric_materialization_readiness_present",
            "metric_materialization_readiness_ready",
            "metric_source_templates_present",
            "metric_source_templates_ready",
            "required_r4_fields_present",
        ],
        "required_int_exact_fields": {
            "authorized_for_external_download": 0,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "execute_command_count": 1,
            "required_r4_field_count": 6,
            "r4_row_count": 17,
            "ready_for_r4_review_row_count": 17,
            "blocked_r4_row_count": 0,
            "target_row_count": 17,
            "source_url_primary_row_count": 17,
            "staging_destination_row_count": 17,
            "fetch_required_row_count": 0,
            "staging_destination_present_row_count": 17,
            "metric_materialization_row_count": 17,
            "metric_materialization_candidate_ready_count": 17,
            "metric_materialization_candidate_blocked_count": 0,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "missing_required_metric_input_artifact_count": 0,
            "planned_metric_source_payload_count": 51,
            "existing_metric_source_payload_count": 0,
            "metric_source_template_row_count": 51,
            "metric_source_template_candidate_row_count": 17,
            "metric_source_template_metric_name_count": 3,
            "metric_source_template_fill_ready_row_count": 51,
            "metric_source_template_fill_blocked_row_count": 0,
            "metric_source_template_existing_payload_present_row_count": 0,
            "metric_materialization_blocked_row_count": 0,
            "missing_r4_field_row_count": 0,
            "download_executed": 0,
            "canonical_intake_promotion_allowed": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "fetch_plan": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json"
            ),
            "fetch_apply": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json"
            ),
            "metric_materialization_readiness": (
                "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
            ),
            "metric_source_templates": (
                "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
            ),
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
            "required_r4_fields": "target;action;impact;risk;rollback;verification",
            "execute_command": (
                "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
                "--mode execute --run-post-fetch-validation "
                "--approval-token APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "next_required_step": (
                "Present Target/Action/Impact/Risk/Rollback/Verification for the 17 public coordinate "
                "fetches to the operator; only after explicit approval run `python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
                "--mode execute --run-post-fetch-validation --approval-token APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD`, "
                "then review coordinate validation before replacing the 51 metric source template placeholders."
            ),
        },
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_semantic_ready"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_COMMAND
        ),
        "required_status": (
            "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
        ),
        "required_true_fields": [
            "receipt_csv_present",
            "r4_preflight_present",
            "r4_preflight_ready",
            "r4_preflight_row_fingerprint_required",
        ],
        "required_int_exact_fields": {
            "operator_receipt_ready": 0,
            "receipt_row_count": 17,
            "required_r4_review_count": 17,
            "missing_required_r4_review_count": 0,
            "unexpected_r4_review_count": 0,
            "duplicate_r4_review_id_count": 0,
            "r4_preflight_row_fingerprint_verified_count": 17,
            "r4_preflight_row_fingerprint_mismatch_count": 0,
            "operator_review_surface_ready_count": 17,
            "operator_review_surface_blocked_count": 0,
            "source_url_present_count": 17,
            "staging_destination_path_present_count": 17,
            "execute_command_present_count": 17,
            "pass_row_count": 0,
            "blocked_row_count": 17,
            "approved_fetch_count": 0,
            "source_url_reviewed_count": 0,
            "license_ok_count": 0,
            "biological_assembly_reviewed_count": 0,
            "post_fetch_validation_required_count": 0,
            "receipt_operator_decision_pending_count": 17,
            "receipt_coordinate_fetch_approval_pending_count": 17,
            "receipt_source_url_review_pending_count": 17,
            "receipt_staging_destination_review_pending_count": 17,
            "receipt_license_review_pending_count": 17,
            "receipt_biological_assembly_review_pending_count": 17,
            "receipt_execute_command_review_pending_count": 17,
            "receipt_post_fetch_validation_review_pending_count": 17,
            "receipt_reviewer_pending_count": 17,
            "receipt_reviewed_at_pending_count": 17,
            "receipt_approval_token_pending_count": 17,
            "receipt_manual_field_pending_count": 187,
            "authorized_for_external_download": 0,
            "download_executed": 0,
            "canonical_intake_promotion_allowed": 0,
            "claim_promotion_allowed": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "receipt_csv": (
                "config/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.csv"
            ),
            "r4_preflight": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
            ),
            "r4_preflight_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            ),
            "first_blocked_review_id": "r9_statistical_support_coordinate_fetch_001",
            "first_blocked_target_id": "4ivc",
            "first_blocked_pose_id": "4ivc_20",
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD",
            "execute_command": (
                "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
                "--mode execute --run-post-fetch-validation "
                "--approval-token APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "next_required_step": (
                "Fill all 17 coordinate-fetch receipt rows "
                "(operator_review_surface_ready_count=17, "
                "receipt_manual_field_pending_count=187, fingerprint_verified_count=17) "
                "with approve_coordinate_fetch, reviewed source/license/assembly fields, reviewer, "
                "timestamp, and APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD; keep claim and canonical "
                "intake promotion flags false."
            ),
        },
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_semantic_ready"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_COMMAND
        ),
        "required_status": (
            "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
        ),
        "required_true_fields": [
            "metric_materialization_readiness_ready",
            "candidate_queue_present",
            "candidate_queue_ready",
            "coordinate_intake_present",
            "coordinate_intake_ready",
            "coordinate_validation_csv_present",
        ],
        "required_int_exact_fields": {
            "metric_materialization_all_candidates_ready": 1,
            "candidate_queue_selected_candidate_count": 17,
            "coordinate_validation_row_count": 17,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "metric_materialization_row_count": 17,
            "metric_materialization_candidate_ready_count": 17,
            "metric_materialization_candidate_blocked_count": 0,
            "metric_materialization_input_artifact_contract_ready": 1,
            "required_metric_input_artifact_count": 34,
            "present_required_metric_input_artifact_count": 34,
            "missing_required_metric_input_artifact_count": 0,
            "missing_required_metric_input_artifact_row_count": 0,
            "required_metric_source_payload_count": 3,
            "metric_source_path_row_count": 17,
            "planned_metric_source_payload_count": 51,
            "existing_metric_source_payload_count": 0,
            "ligand_pose_artifact_present_count": 17,
            "experimental_deltaG_prefilled_count": 17,
            "candidate_ready_for_canonical_intake_count": 0,
            "claim_grade_statistical_support_ready": 0,
            "canonical_intake_promotion_allowed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "candidate_queue": (
                "runs/refine_tier_public_benchmark_statistical_support_candidate_queue_current.json"
            ),
            "coordinate_intake": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json"
            ),
            "coordinate_validation_csv": (
                "runs/refine_tier_public_benchmark_statistical_support_coordinate_validation_current.csv"
            ),
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "next_required_step": (
                "All 17 statistical-support candidates have coordinate validation and required input "
                "artifacts ready; fill/review the 51 DockQ/lDDT-PLI/internal DeltaG metric source payloads, "
                "materialize them, and rerun bootstrap Spearman p05 before any R9 claim receipt or canonical "
                "intake promotion."
            ),
        },
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_source_templates_semantic_ready"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_COMMAND
        ),
        "required_status": (
            "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
        ),
        "required_true_fields": [
            "metric_source_templates_ready",
            "metric_materialization_readiness_present",
            "metric_materialization_readiness_ready",
        ],
        "required_int_exact_fields": {
            "metric_materialization_row_count": 17,
            "metric_materialization_candidate_ready_count": 17,
            "metric_materialization_candidate_blocked_count": 0,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "planned_metric_source_payload_count": 51,
            "existing_metric_source_payload_count": 0,
            "template_row_count": 51,
            "template_candidate_row_count": 17,
            "template_metric_name_count": 3,
            "template_metric_source_artifact_path_row_count": 51,
            "template_payload_required_fields_present_row_count": 51,
            "metric_source_payload_fill_ready_row_count": 51,
            "metric_source_payload_fill_blocked_row_count": 0,
            "coordinate_validation_blocked_template_row_count": 0,
            "missing_required_input_template_row_count": 0,
            "existing_metric_source_payload_present_row_count": 0,
            "required_metric_source_payload_count": 3,
            "required_metric_source_payload_field_count": 11,
            "placeholder_value_count": 51,
            "placeholder_method_count": 51,
            "placeholder_operator_id_count": 51,
            "placeholder_reviewed_at_utc_count": 51,
            "placeholder_license_ok_count": 51,
            "external_engine_calls_total": 0,
            "canonical_intake_promotion_allowed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 0,
        },
        "required_text_exact_fields": {
            "metric_materialization_readiness": (
                "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
            ),
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
            "next_required_step": (
                "With coordinate fetch and validation ready, replace each operator placeholder with "
                "reviewed DockQ/lDDT-PLI/internal DeltaG values while preserving input artifact paths, "
                "hashes, license_ok=true, and external_engine_calls=0."
            ),
        },
    },
    {
        "artifact_id": (
            "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_semantic_ready"
        ),
        "artifact_path": (
            "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
        ),
        "builder_command": (
            REFINE_TIER_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_COMMAND
        ),
        "required_status": (
            "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
        ),
        "required_true_fields": [
            "receipt_csv_present",
            "metric_source_templates_present",
            "metric_source_templates_ready",
            "metric_source_template_row_fingerprint_required",
        ],
        "required_int_exact_fields": {
            "operator_receipt_ready": 0,
            "receipt_row_count": 51,
            "required_template_count": 51,
            "missing_required_template_count": 0,
            "unexpected_template_count": 0,
            "duplicate_template_id_count": 0,
            "metric_source_template_row_fingerprint_verified_count": 51,
            "metric_source_template_row_fingerprint_mismatch_count": 0,
            "operator_review_surface_ready_count": 51,
            "operator_review_surface_blocked_count": 0,
            "metric_source_artifact_path_present_count": 51,
            "required_metric_input_artifact_list_present_count": 51,
            "required_metric_input_artifact_sha256_list_present_count": 51,
            "required_metric_input_artifact_sha256_list_complete_count": 51,
            "required_metric_source_payload_fields_present_count": 51,
            "external_engine_calls_zero_count": 51,
            "receipt_manual_field_pending_count": 510,
            "receipt_metric_value_pending_count": 51,
            "receipt_approval_token_pending_count": 51,
            "pass_row_count": 0,
            "blocked_row_count": 51,
            "approved_payload_count": 0,
            "template_fill_ready_row_count": 51,
            "coordinate_validation_pass_payload_row_count": 51,
            "coordinate_validation_blocked_payload_row_count": 0,
            "payload_write_allowed": 0,
            "canonical_intake_promotion_allowed": 0,
            "claim_promotion_allowed": 0,
            "external_state_mutated": 0,
            "blocker_count": 1,
        },
        "required_text_exact_fields": {
            "receipt_csv": (
                "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
            ),
            "metric_source_templates": (
                "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
            ),
            "metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "first_blocked_template_id": "r9_statistical_support_metric_source_template_001",
            "first_blocked_target_id": "4ivc",
            "first_blocked_pose_id": "4ivc_20",
            "first_blocked_metric_name": "dockq",
            "most_common_row_blocker": "operator_placeholders_unfilled",
            "approval_token_required": "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS",
        },
    },
    {
        "artifact_id": "refine_tier_public_benchmark_claim_grade_gap_audit_semantic_ready",
        "artifact_path": "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json",
        "builder_command": REFINE_TIER_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_COMMAND,
        "required_status": "refine_tier_public_benchmark_claim_grade_gap_audit_ready",
        "required_true_fields": [
            "claim_grade_gap_audit_ready",
            "materialization_artifact_present",
            "statistical_support_work_order_present",
            "metric_materialization_readiness_present",
            "metric_source_templates_present",
            "coordinate_fetch_r4_preflight_present",
            "coordinate_fetch_r4_preflight_ready",
            "bootstrap_retest_required",
        ],
        "required_int_exact_fields": {
            "claim_grade_statistical_support_ready": 0,
            "canonical_intake_promotion_allowed": 0,
            "observed_public_benchmark_pair_count": 25,
            "observed_holdout_pair_count": 8,
            "min_claim_grade_public_benchmark_pairs_required": 25,
            "min_claim_grade_holdout_pairs_required": 8,
            "minimum_new_pair_count": 0,
            "minimum_new_holdout_pair_count": 0,
            "statistical_support_work_order_expansion_slot_count": 17,
            "statistical_support_work_order_holdout_expansion_slot_count": 5,
            "statistical_support_work_order_fit_or_holdout_expansion_slot_count": 12,
            "coordinate_fetch_r4_fetch_required_row_count": 0,
            "coordinate_fetch_r4_ready_for_review_row_count": 17,
            "coordinate_fetch_r4_blocked_row_count": 0,
            "coordinate_fetch_r4_authorized_for_external_download": 0,
            "coordinate_fetch_r4_download_executed": 0,
            "coordinate_fetch_r4_external_state_mutated": 0,
            "coordinate_validation_candidate_row_count": 17,
            "coordinate_validation_pass_row_count": 17,
            "coordinate_validation_blocked_row_count": 0,
            "coordinate_validation_deficit": 0,
            "planned_metric_source_payload_count": 51,
            "metric_source_payload_fill_ready_row_count": 51,
            "metric_source_payload_fill_blocked_row_count": 0,
            "metric_source_payload_fill_deficit": 0,
            "gap_row_count": 5,
            "blocked_gap_row_count": 1,
            "pass_gap_row_count": 4,
            "blocker_count": 1,
            "execution_enabled": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "observed_bootstrap_spearman_p05": "0.23349188084975714",
            "bootstrap_spearman_p05_deficit": "0.26650811915024286",
            "coordinate_fetch_r4_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "required_metric_source_payloads": "dockq;lddt_pli;internal_deltaG",
            "required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
            "top_science_gap_id": "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
            "top_statistical_gap_id": "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
            "next_required_step": (
                "The 17-candidate preview fills 51/51 metric values and closes the 25-pair/8-holdout "
                "quantity gaps, but bootstrap Spearman p05 remains below 0.5 and the preview has not "
                "written reviewed metric source payloads. Keep R9 claim-grade promotion blocked; improve "
                "candidate/score quality, then require operator-reviewed payload receipt before canonical "
                "intake promotion."
            ),
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
            "public_benchmark_statistical_support_work_order_present",
            "public_benchmark_statistical_support_work_order_ready",
            "public_benchmark_statistical_support_metric_materialization_readiness_present",
            "public_benchmark_statistical_support_metric_materialization_readiness_ready",
            "public_benchmark_statistical_support_coordinate_intake_present",
            "public_benchmark_statistical_support_coordinate_intake_ready",
            "public_benchmark_statistical_support_metric_source_templates_present",
            "public_benchmark_statistical_support_metric_source_templates_ready",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_present",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready",
            "public_benchmark_claim_grade_gap_audit_present",
            "public_benchmark_claim_grade_gap_audit_ready",
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
            "public_benchmark_materialized_candidate_ready": 1,
            "public_benchmark_materialized_claim_grade_statistical_support_ready": 0,
            "public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready": 0,
            "public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count": 25,
            "public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count": 8,
            "public_benchmark_claim_grade_gap_audit_minimum_new_pair_count": 0,
            "public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count": 0,
            "public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count": 17,
            "public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count": 51,
            "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count": 0,
            "public_benchmark_claim_grade_gap_audit_gap_row_count": 5,
            "public_benchmark_claim_grade_gap_audit_blocked_gap_row_count": 1,
            "public_benchmark_claim_grade_gap_audit_blocker_count": 1,
            "public_benchmark_statistical_support_work_order_expansion_slot_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_pair_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": 5,
            "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": 12,
            "public_benchmark_statistical_support_work_order_bootstrap_retest_required": 1,
            "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_materialization_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_ready_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": 0,
            "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": 1,
            "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": 0,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": 0,
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": 11,
            "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready": 0,
            "public_benchmark_statistical_support_coordinate_intake_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_missing_row_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": 136,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": 51,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "public_benchmark_statistical_support_coordinate_fetch_r4_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": 0,
            "approval_token_count": 1,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV,
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "public_benchmark_statistical_support_work_order_status": (
                "refine_tier_public_benchmark_statistical_support_work_order_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_status": (
                "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": (
                "dockq;lddt_pli;internal_deltaG"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;"
                "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;"
                "external_engine_calls"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_csv": (
                R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "public_benchmark_statistical_support_coordinate_intake_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "public_benchmark_claim_grade_gap_audit_status": (
                "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
            ),
            "public_benchmark_claim_grade_gap_audit_top_science_gap_id": (
                "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum"
            ),
            "public_benchmark_claim_grade_gap_audit_top_statistical_gap_id": (
                "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum"
            ),
            "top_next_operator_step": (
                "Coordinate fetch and validation are complete "
                "(r4_ready_for_review_row_count=17, r4_blocked_row_count=0, fetch_required_row_count=0, "
                "approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD) for 17 "
                "statistical-support candidates (coordinate_validation_pass_row_count=17, "
                "metric_materialization_candidate_ready_count=17, required_input_artifacts=34/34/0, "
                "local_coordinate_present_targets=17, local_coordinate_missing_targets=0, "
                "planned_metric_source_payload_count=51); fill and review the 51 DockQ/lDDT-PLI/internal "
                "DeltaG metric source payloads, materialize them, and rerun bootstrap Spearman p05 before "
                "any R9 claim receipt or canonical intake promotion."
            ),
        },
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_operator_field_worksheet_semantic_ready",
        "artifact_path": "runs/engine_refinement_claim_evidence_operator_field_worksheet_current.json",
        "builder_command": (
            "python3 tools/build_engine_refinement_claim_evidence_operator_field_worksheet.py"
        ),
        "required_status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
        "required_true_fields": [
            "field_worksheet_ready",
            "receipt_csv_present",
            "receipt_artifact_present",
            "priority_packet_artifact_present",
            "public_benchmark_readiness_artifact_present",
            "public_benchmark_work_order_csv_present",
            "public_benchmark_work_order_apply_artifact_present",
            "public_benchmark_statistical_support_work_order_artifact_present",
            "public_benchmark_statistical_support_work_order_ready",
            "public_benchmark_statistical_support_metric_materialization_readiness_artifact_present",
            "public_benchmark_statistical_support_metric_materialization_readiness_ready",
            "public_benchmark_statistical_support_coordinate_intake_artifact_present",
            "public_benchmark_statistical_support_coordinate_intake_ready",
            "public_benchmark_statistical_support_metric_source_templates_artifact_present",
            "public_benchmark_statistical_support_metric_source_templates_ready",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_present",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_artifact_present",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_csv_present",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required",
        ],
        "required_int_exact_fields": {
            "operator_fill_complete": 0,
            "receipt_row_count": 6,
            "receipt_field_row_count": 72,
            "required_receipt_field_count": 66,
            "receipt_operator_fill_pending_field_count": 36,
            "public_benchmark_work_order_row_count": 8,
            "public_benchmark_work_order_field_count": 96,
            "public_benchmark_work_order_pending_field_count": 56,
            "worksheet_field_row_count": 389,
            "operator_fill_pending_field_count": 296,
            "invalid_field_count": 0,
            "top_blocker_field_count": 329,
            "top_blocker_pending_field_count": 266,
            "public_benchmark_gate_ready": 0,
            "public_benchmark_work_order_apply_ready": 0,
            "public_benchmark_work_order_apply_blocked_row_count": 8,
            "public_benchmark_materialized_science_evidence_complete": 1,
            "public_benchmark_materialized_claim_grade_statistical_support_ready": 0,
            "public_benchmark_statistical_support_work_order_expansion_slot_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_pair_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": 5,
            "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": 12,
            "public_benchmark_statistical_support_work_order_bootstrap_retest_required": 1,
            "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_expansion_slot_row_count": 17,
            "public_benchmark_statistical_support_expansion_holdout_slot_count": 5,
            "public_benchmark_statistical_support_expansion_fit_or_holdout_slot_count": 12,
            "public_benchmark_statistical_support_expansion_field_count": 221,
            "public_benchmark_statistical_support_expansion_pending_field_count": 204,
            "public_benchmark_statistical_support_expansion_ready_field_count": 17,
            "public_benchmark_statistical_support_metric_materialization_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_ready_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": 0,
            "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": 1,
            "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": 0,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": 0,
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": 11,
            "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready": 0,
            "public_benchmark_statistical_support_coordinate_intake_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_missing_row_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": 136,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": 51,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": 17,
            "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": 3,
            "public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_value_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_method_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_operator_id_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_reviewed_at_utc_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_license_ok_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": 0,
            "public_benchmark_statistical_support_metric_source_templates_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_metric_source_artifact_path_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_list_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_complete_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_source_payload_fields_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_engine_calls_zero_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count": 510,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_value_pending_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_approval_token_pending_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_claim_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_state_mutated": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": 1,
            "public_benchmark_statistical_support_coordinate_fetch_r4_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_source_url_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_staging_destination_path_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count": 187,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_claim_promotion_allowed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_external_state_mutated": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": 1,
            "public_benchmark_metric_evidence_missing_required_input_artifact_row_count": 0,
            "public_benchmark_metric_evidence_missing_required_input_artifact_sha256_row_count": 0,
            "claim_promotion_allowed": 0,
            "claim_promoted": 0,
            "intake_written": 0,
            "external_engine_calls_executed": 0,
            "external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
            "priority_packet_status": "blocked_engine_refinement_claim_evidence_priority_packet",
            "public_benchmark_status": "blocked_refine_tier_public_benchmark_readiness",
            "public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": "public_benchmark_work_order_apply_required",
            "top_required_input": R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV,
            "public_benchmark_statistical_support_work_order_status": (
                "refine_tier_public_benchmark_statistical_support_work_order_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_status": (
                "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": (
                "dockq;lddt_pli;internal_deltaG"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;"
                "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;"
                "external_engine_calls"
            ),
            "public_benchmark_statistical_support_coordinate_intake_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
            ),
            "public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": (
                "dockq"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": (
                "r9_statistical_support_coordinate_fetch_001"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": (
                "4ivc"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": (
                "4ivc_20"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "next_required_step": (
                "Coordinate fetch and validation are complete (coordinate_validation_pass_row_count=17, "
                "metric_materialization_candidate_ready_count=17, required_input_artifacts=34/34/0, "
                "local_coordinate_present_targets=17, local_coordinate_missing_targets=0, "
                "planned_metric_source_payload_count=51); fill/approve the 51-row metric payload "
                "operator receipt (receipt_blocked_row_count=51, operator_review_surface_ready_count=51, "
                "receipt_manual_field_pending_count=510, "
                "approval_token_required=APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS) and "
                "materialize DockQ/lDDT-PLI/internal DeltaG source payloads before rerunning bootstrap "
                "Spearman p05 ahead of any R9 claim receipt or canonical intake promotion."
            ),
            "approval_token_required": "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT",
        },
    },
    {
        "artifact_id": "engine_refinement_claim_evidence_operator_staging_apply_blocked_semantic_ready",
        "artifact_path": "runs/engine_refinement_claim_evidence_operator_staging_apply_current.json",
        "builder_command": (
            "python3 tools/build_engine_refinement_claim_evidence_operator_staging_apply.py"
        ),
        "required_status": "blocked_engine_refinement_claim_evidence_operator_staging_apply",
        "required_true_fields": [
            "staging_receipt_csv_present",
            "live_receipt_csv_present",
            "staging_public_benchmark_work_order_csv_present",
            "existing_public_benchmark_work_order_apply_artifact_present",
            "field_worksheet_present",
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_artifact_present",
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready",
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present",
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required",
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present",
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required",
        ],
        "required_int_exact_fields": {
            "staging_receipt_row_count": 6,
            "staging_receipt_missing_required_column_count": 0,
            "staging_receipt_placeholder_row_count": 6,
            "live_receipt_row_count": 6,
            "candidate_receipt_written": 0,
            "candidate_receipt_ready": 0,
            "candidate_receipt_pass_row_count": 0,
            "candidate_receipt_blocked_row_count": 6,
            "candidate_receipt_blocker_count": 1,
            "staging_public_benchmark_work_order_row_count": 8,
            "staging_public_benchmark_work_order_missing_required_column_count": 0,
            "staging_public_benchmark_work_order_placeholder_row_count": 8,
            "candidate_public_benchmark_work_order_ready": 0,
            "candidate_public_benchmark_valid_intake_row_count": 0,
            "candidate_public_benchmark_blocked_row_count": 8,
            "candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count": 0,
            "candidate_public_benchmark_metric_evidence_missing_required_receptor_input_row_count": 0,
            "candidate_public_benchmark_metric_evidence_required_input_sha256_blocked_row_count": 0,
            "candidate_public_benchmark_candidate_intake_written": 0,
            "field_worksheet_pending_field_count": 296,
            "field_worksheet_receipt_pending_field_count": 36,
            "field_worksheet_work_order_pending_field_count": 56,
            "field_worksheet_top_blocker_pending_field_count": 266,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": 17,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": 3,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_metric_source_artifact_path_present_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_list_present_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_present_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_complete_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_source_payload_fields_present_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_engine_calls_zero_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count": 510,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_value_pending_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_approval_token_pending_count": 51,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": 0,
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": 1,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": 17,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": 17,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": 17,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": 17,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count": 17,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count": 187,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": 0,
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": 1,
            "approval_token_present": 0,
            "approval_token_accepted": 0,
            "public_benchmark_approval_token_present": 0,
            "public_benchmark_approval_token_accepted": 0,
            "live_copy_allowed": 0,
            "public_benchmark_intake_write_allowed": 0,
            "write_canonical_receipt_requested": 0,
            "write_public_benchmark_intake_requested": 0,
            "canonical_receipt_written": 0,
            "public_benchmark_intake_written": 0,
            "claim_promotion_allowed": 0,
            "claim_promoted": 0,
            "external_engine_calls_executed": 0,
            "execution_enabled": 0,
            "external_state_mutated": 0,
            "blocker_count": 2,
        },
        "required_text_exact_fields": {
            "mode": "preview",
            "staging_receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "live_receipt_csv": "config/engine_refinement_claim_promotion_evidence_receipt_current.csv",
            "candidate_receipt_csv": "runs/engine_refinement_claim_evidence_receipt_candidate_current.csv",
            "candidate_receipt_status": "blocked_engine_refinement_claim_evidence_receipt",
            "candidate_first_blocked_blocker_id": "public_benchmark_gate_not_ready",
            "candidate_first_blocked_evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "candidate_first_blocked_expected_evidence_status": "refine_tier_public_benchmark_ready",
            "candidate_first_blocked_observed_evidence_status": "missing",
            "candidate_most_common_row_blocker": "operator_placeholders_unfilled",
            "staging_public_benchmark_work_order_csv": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "candidate_public_benchmark_intake_csv": (
                "runs/engine_refinement_claim_evidence_public_benchmark_intake_candidate_current.csv"
            ),
            "candidate_public_benchmark_work_order_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "existing_public_benchmark_work_order_apply_status": (
                "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "field_worksheet_status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
            "field_worksheet_top_blocker_id": "public_benchmark_gate_not_ready",
            "field_worksheet_top_priority_bucket": "public_benchmark_work_order_apply_required",
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
            ),
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": (
                "dockq"
            ),
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": (
                "r9_statistical_support_coordinate_fetch_001"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": (
                "4ivc"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": (
                "4ivc_20"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "next_required_step": (
                "Materialized public benchmark science candidate is ready but not claim-grade, and R9 "
                "statistical-support coordinate fetch/validation is complete: fill/approve 51 metric "
                "payload receipt rows (operator_review_surface_ready_count=51, "
                "receipt_manual_field_pending_count=510, "
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS), materialize the "
                "DockQ/lDDT-PLI/internal DeltaG source payloads, and rerun bootstrap Spearman p05 before "
                "any canonical R9 receipt or public benchmark intake promotion."
            ),
        },
    },
    {
        "artifact_id": "science_accuracy_frontier_restricted_ready_commercial_parity_blocked",
        "artifact_path": "runs/science_accuracy_frontier_current.json",
        "builder_command": "python3 tools/product/build_science_accuracy_frontier.py",
        "required_status": "blocked_science_accuracy_frontier",
        "required_true_fields": [
            "restricted_science_accuracy_ready",
            "gpcr_ligand_metric_ready",
            "gpcr_target_heldout_guarded_inputs_ready",
            "engine_refinement_internal_surface_ready",
            "engine_refinement_claim_evidence_priority_packet_ready",
            "pose_sampling_contract_ready",
            "public_benchmark_materialized_metric_ready",
            "public_benchmark_materialized_apply_ready",
            "public_benchmark_statistical_support_work_order_ready",
            "public_benchmark_statistical_support_metric_materialization_readiness_present",
            "public_benchmark_statistical_support_metric_materialization_readiness_ready",
            "public_benchmark_statistical_support_metric_source_templates_present",
            "public_benchmark_statistical_support_metric_source_templates_ready",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_present",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_csv_present",
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present",
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_csv_present",
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required",
            "public_benchmark_claim_grade_gap_audit_present",
            "public_benchmark_claim_grade_gap_audit_ready",
            "public_benchmark_bootstrap_driver_operator_chain_rollup_present",
            "public_benchmark_bootstrap_driver_operator_chain_surface_ready",
        ],
        "required_int_exact_fields": {
            "broad_commercial_accuracy_claim_ready": 0,
            "gpcr_broad_claim_ready": 0,
            "gpcr_scorer_router_ready": 0,
            "gpcr_broad_claim_review_receipt_ready": 0,
            "gpcr_broad_claim_review_receipt_row_count": 2,
            "gpcr_broad_claim_review_receipt_pass_row_count": 0,
            "gpcr_broad_claim_review_receipt_blocked_row_count": 2,
            "gpcr_broad_claim_review_receipt_operator_review_surface_ready_count": 2,
            "gpcr_broad_claim_review_receipt_operator_review_surface_blocked_count": 0,
            "gpcr_broad_claim_review_receipt_evidence_artifact_present_count": 0,
            "gpcr_broad_claim_review_receipt_evidence_status_contract_present_count": 2,
            "gpcr_broad_claim_review_receipt_expected_true_fields_present_count": 2,
            "gpcr_broad_claim_review_receipt_external_engine_calls_zero_count": 2,
            "gpcr_broad_claim_review_receipt_manual_field_pending_count": 16,
            "gpcr_active_scorer_gate_ready": 0,
            "gpcr_scorer_router_promotion_gate_receipt_approved": 0,
            "openmm_schrodinger_public_benchmark_ready": 0,
            "openmm_schrodinger_claim_ready": 0,
            "engine_refinement_claim_evidence_receipt_ready": 0,
            "accuracy_metric_blocker_count": 0,
            "gpcr_broad_claim_blocker_count": 2,
            "engine_refinement_claim_blocker_count": 6,
            "public_benchmark_blocker_count": 6,
            "public_benchmark_required_row_count": 8,
            "public_benchmark_current_row_count": 0,
            "public_benchmark_work_order_row_count": 8,
            "public_benchmark_work_order_seeded_row_count": 8,
            "public_benchmark_work_order_prefilled_operator_field_count": 40,
            "public_benchmark_work_order_pending_operator_field_count": 56,
            "public_benchmark_work_order_experimental_deltaG_prefilled_count": 8,
            "public_benchmark_work_order_experimental_deltaG_source_parsed_count": 285,
            "public_benchmark_work_order_pending_license_ok_count": 8,
            "public_benchmark_work_order_pending_dockq_count": 8,
            "public_benchmark_work_order_pending_lddt_pli_count": 8,
            "public_benchmark_work_order_pending_internal_deltaG_count": 8,
            "public_benchmark_work_order_pending_experimental_deltaG_count": 0,
            "public_benchmark_work_order_remaining_nonlicense_science_field_count": 48,
            "public_benchmark_work_order_current_local_source_prefill_ready_field_count": 0,
            "public_benchmark_work_order_local_receptor_coordinate_file_count": 25,
            "public_benchmark_work_order_tar_ligand_pose_member_count": 23062,
            "public_benchmark_work_order_tar_receptor_coordinate_member_count": 0,
            "public_benchmark_work_order_tar_ligand_only_archive_count": 2,
            "public_benchmark_work_order_science_input_gap_row_count": 8,
            "public_benchmark_work_order_science_input_gap_blocked_row_count": 8,
            "public_benchmark_work_order_local_ligand_pose_artifact_count": 8,
            "public_benchmark_work_order_missing_ligand_pose_artifact_count": 0,
            "public_benchmark_work_order_receptor_coordinate_ready_row_count": 8,
            "public_benchmark_work_order_missing_receptor_coordinate_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_intake_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_intake_matched_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_intake_missing_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_intake_suggested_public_url_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_intake_suggested_local_path_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_intake_operator_review_required_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_validation_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_validation_ready_row_count": 8,
            "public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_validation_missing_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_validation_below_min_atom_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_validation_below_min_macromolecule_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_validation_below_min_protein_like_row_count": 0,
            "public_benchmark_work_order_receptor_coordinate_validation_min_atom_records": 20,
            "public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records": 20,
            "public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues": 5,
            "public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues": 5,
            "public_benchmark_work_order_metric_evidence_required": 1,
            "public_benchmark_work_order_metric_evidence_row_count": 8,
            "public_benchmark_work_order_metric_evidence_ready_row_count": 0,
            "public_benchmark_work_order_metric_evidence_blocked_row_count": 8,
            "public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count": 8,
            "public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count": 8,
            "public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count": 8,
            "public_benchmark_materialized_row_count": 8,
            "public_benchmark_materialized_blocked_row_count": 0,
            "public_benchmark_materialized_metric_evidence_pass_row_count": 8,
            "public_benchmark_materialized_metric_evidence_blocked_row_count": 0,
            "public_benchmark_materialized_free_energy_pair_count": 8,
            "public_benchmark_materialized_free_energy_fit_pair_count": 5,
            "public_benchmark_materialized_free_energy_holdout_pair_count": 3,
            "public_benchmark_materialized_free_energy_unknown_split_pair_count": 0,
            "public_benchmark_materialized_free_energy_spearman_gate_ready": 1,
            "public_benchmark_materialized_claim_grade_statistical_support_ready": 0,
            "public_benchmark_materialized_claim_grade_statistical_support_blocker_count": 3,
            "public_benchmark_materialized_min_claim_grade_public_benchmark_pairs_required": 25,
            "public_benchmark_materialized_min_claim_grade_holdout_pairs_required": 8,
            "public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready": 0,
            "public_benchmark_claim_grade_gap_audit_canonical_intake_promotion_allowed": 0,
            "public_benchmark_claim_grade_gap_audit_bootstrap_retest_required": 1,
            "public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count": 25,
            "public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count": 8,
            "public_benchmark_claim_grade_gap_audit_minimum_new_pair_count": 0,
            "public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count": 0,
            "public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count": 17,
            "public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_claim_grade_gap_audit_coordinate_validation_deficit": 0,
            "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count": 51,
            "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count": 0,
            "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_deficit": 0,
            "public_benchmark_claim_grade_gap_audit_planned_metric_source_payload_count": 51,
            "public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_fetch_required_row_count": 0,
            "public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_download_executed": 0,
            "public_benchmark_claim_grade_gap_audit_gap_row_count": 5,
            "public_benchmark_claim_grade_gap_audit_blocked_gap_row_count": 1,
            "public_benchmark_claim_grade_gap_audit_pass_gap_row_count": 4,
            "public_benchmark_claim_grade_gap_audit_blocker_count": 1,
            "public_benchmark_materialized_apply_blocked_row_count": 0,
            "public_benchmark_materialized_apply_metric_evidence_pass_row_count": 8,
            "public_benchmark_materialized_apply_metric_evidence_contract_blocked_row_count": 0,
            "public_benchmark_statistical_support_work_order_expansion_slot_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_pair_count": 17,
            "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": 5,
            "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": 12,
            "public_benchmark_statistical_support_work_order_bootstrap_retest_required": 1,
            "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_materialization_all_candidates_ready": 1,
            "public_benchmark_statistical_support_metric_materialization_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_ready_count": 17,
            "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": 0,
            "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": 1,
            "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": 34,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": 0,
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": 0,
            "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": 11,
            "public_benchmark_statistical_support_coordinate_intake_ready": 1,
            "public_benchmark_statistical_support_coordinate_intake_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_missing_row_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_suggested_public_url_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": 136,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": 51,
            "public_benchmark_statistical_support_coordinate_intake_operator_review_required_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": 17,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_missing_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": 17,
            "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": 3,
            "public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": 0,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_value_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_method_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_operator_id_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_reviewed_at_utc_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_placeholder_license_ok_count": 51,
            "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": 0,
            "public_benchmark_statistical_support_metric_source_templates_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_fill_ready_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_ready_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_operator_review_surface_blocked_count": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_metric_source_artifact_path_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_list_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_input_artifact_sha256_list_complete_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_metric_source_payload_fields_present_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_engine_calls_zero_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_manual_field_pending_count": 510,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_metric_value_pending_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_approval_token_pending_count": 51,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_claim_promotion_allowed": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_external_state_mutated": 0,
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": 1,
            "public_benchmark_statistical_support_coordinate_fetch_r4_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": 51,
            "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_ready_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_operator_review_surface_blocked_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_source_url_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_staging_destination_path_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command_present_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_receipt_manual_field_pending_count": 187,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": 17,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_canonical_intake_promotion_allowed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_claim_promotion_allowed": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_external_state_mutated": 0,
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": 1,
            "public_benchmark_bootstrap_driver_operator_chain_closure_ready": 0,
            "public_benchmark_bootstrap_driver_operator_chain_stage_count": 5,
            "public_benchmark_bootstrap_driver_operator_chain_stage_artifact_present_count": 5,
            "public_benchmark_bootstrap_driver_operator_chain_stage_surface_ready_count": 4,
            "public_benchmark_bootstrap_driver_operator_chain_source_staging_operator_manual_pending_field_count": 66,
            "public_benchmark_bootstrap_driver_operator_chain_machine_supported_prefilled_field_count": 36,
            "public_benchmark_bootstrap_driver_operator_chain_operator_only_pending_field_count": 30,
            "public_benchmark_bootstrap_driver_operator_chain_attestation_blocked_row_count": 6,
            "public_benchmark_bootstrap_driver_operator_chain_attestation_merge_ready": 0,
            "public_benchmark_bootstrap_driver_operator_chain_merge_preview_blocked_row_count": 6,
            "public_benchmark_bootstrap_driver_operator_chain_prefill_row_fingerprint_verified_count": 6,
            "public_benchmark_bootstrap_driver_operator_chain_prefill_row_fingerprint_mismatch_count": 0,
            "public_benchmark_bootstrap_driver_operator_chain_merged_candidate_row_count": 0,
            "public_benchmark_bootstrap_driver_operator_chain_blocker_count": 3,
            "public_benchmark_work_order_ligand_pose_only_row_count": 0,
            "public_benchmark_work_order_missing_interaction_metric_source_row_count": 8,
            "public_benchmark_work_order_missing_internal_deltaG_source_row_count": 8,
            "public_benchmark_work_order_seed_interaction_metric_column_count": 0,
            "public_benchmark_work_order_seed_internal_deltaG_column_count": 0,
            "public_benchmark_work_order_seed_candidate_row_count": 8,
            "public_benchmark_work_order_seed_distinct_target_count": 8,
            "engine_refinement_receipt_blocked_row_count": 6,
            "external_state_mutated": 0,
            "blocker_count": 7,
        },
        "required_text_exact_fields": {
            "accuracy_parity_status": "blocked_accuracy_parity",
            "gpcr_broad_claim_scope_status": "blocked_gpcr_broad_claim_scope_readiness",
            "gpcr_broad_claim_review_receipt_status": "blocked_gpcr_broad_claim_review_receipt",
            "gpcr_broad_claim_review_receipt_first_blocked_review_id": (
                "target_heldout_broad_scope_review_not_approved"
            ),
            "gpcr_broad_claim_review_receipt_approval_token_required": "APPROVE_GPCR_BROAD_CLAIM_REVIEW",
            "engine_refinement_tier_status": "engine_refinement_tier_ready",
            "refine_tier_public_benchmark_status": "blocked_refine_tier_public_benchmark_readiness",
            "public_benchmark_statistical_support_work_order_status": (
                "refine_tier_public_benchmark_statistical_support_work_order_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_status": (
                "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": (
                "dockq;lddt_pli;internal_deltaG"
            ),
            "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
                "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
            ),
            "public_benchmark_statistical_support_coordinate_intake_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
            ),
            "public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_target_id": (
                "4ivc"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_pose_id": (
                "4ivc_20"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": (
                "dockq"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": (
                "r9_statistical_support_coordinate_fetch_001"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": (
                "4ivc"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": (
                "4ivc_20"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "public_benchmark_claim_grade_gap_audit_status": (
                "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
            ),
            "public_benchmark_claim_grade_gap_audit_top_science_gap_id": (
                "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum"
            ),
            "public_benchmark_claim_grade_gap_audit_top_statistical_gap_id": (
                "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum"
            ),
            "public_benchmark_bootstrap_driver_operator_chain_status": (
                "blocked_refine_tier_public_benchmark_bootstrap_driver_operator_chain_rollup"
            ),
            "public_benchmark_bootstrap_driver_operator_chain_final_blocker_stage_id": (
                "attestation_merge_preview"
            ),
            "public_benchmark_bootstrap_driver_operator_chain_final_blocker": (
                "operator_only_placeholders_unfilled"
            ),
            "engine_refinement_claim_evidence_receipt_status": (
                "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "engine_refinement_claim_evidence_priority_packet_status": (
                "blocked_engine_refinement_claim_evidence_priority_packet"
            ),
            "product_pose_sampling_readiness_status": "product_pose_sampling_readiness_ready",
            "engine_refinement_priority_top_blocker_id": "public_benchmark_gate_not_ready",
            "engine_refinement_priority_top_required_input": R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV,
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
            "scope_receipt_operator_review_surface_ready_count": 6,
            "scope_receipt_operator_review_surface_blocked_count": 0,
            "scope_receipt_manual_field_pending_count": 36,
            "scope_receipt_evidence_status_contract_present_count": 6,
            "scope_receipt_expected_true_fields_present_count": 6,
            "scope_receipt_provenance_kind_accepted_count": 6,
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
            "primary_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
            "primary_action_required_input": (
                "production_promotion_allowed;customer_facing_auto_correction_allowed;"
                "customer_facing_score_mutation_allowed;customer_facing_ranking_mutation_allowed;"
                "default_residual_mode;trained_model_checkpoint_count"
            ),
            "primary_action_status": "required",
        },
    },
    {
        "artifact_id": "goal_operator_intake_kit_primary_release_blocker_semantic_ready",
        "artifact_path": "runs/goal_operator_intake_kit_current/manifest.json",
        "builder_command": "python3 tools/build_goal_operator_intake_kit.py",
        "required_status": "goal_operator_intake_kit_ready",
        "required_true_fields": [
            "product_scope_breadth_evidence_priority_packet_ready",
            "production_ai_registry_promotion_priority_packet_ready",
        ],
        "required_int_exact_fields": {
            "product_goal_release_blocker_fail_count": 2,
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
            "production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
            "product_scope_breadth_evidence_priority_open_item_count": 15,
            "product_scope_breadth_evidence_priority_scientific_evidence_request_count": 11,
            "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count": 11,
            "product_scope_breadth_evidence_priority_review_only_keep_blocked_count": 1,
            "product_scope_breadth_evidence_priority_receipt_row_count": 6,
            "product_scope_breadth_evidence_priority_receipt_blocked_row_count": 6,
            "product_scope_breadth_evidence_priority_receipt_operator_review_surface_ready_count": 6,
            "product_scope_breadth_evidence_priority_receipt_operator_review_surface_blocked_count": 0,
            "product_scope_breadth_evidence_priority_receipt_manual_field_pending_count": 36,
            "product_scope_breadth_evidence_priority_receipt_evidence_artifact_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_claim_ready_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_reviewer_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_reviewed_at_utc_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_license_ok_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_approval_token_pending_count": 6,
        },
        "required_text_exact_fields": {
            "product_scope_breadth_evidence_priority_source_json": (
                "runs/product_scope_breadth_evidence_priority_packet_current.json"
            ),
            "product_scope_breadth_evidence_priority_status": (
                "product_scope_breadth_evidence_priority_packet_ready"
            ),
            "product_scope_breadth_evidence_priority_top_item_id": "AQP1.core_binder_01",
            "product_scope_breadth_evidence_priority_top_domain": "transporter",
            "product_scope_breadth_evidence_priority_top_bucket": (
                "local_crosscheck_review_present_but_exact_quant_required"
            ),
            "product_scope_breadth_evidence_priority_top_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_breadth_evidence_priority_receipt_status": (
                "blocked_product_scope_breadth_evidence_receipt"
            ),
            "product_scope_breadth_evidence_priority_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_scope_blocker_id": (
                "direct_binding_evidence_missing"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_scope_breadth_evidence_priority_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "product_scope_breadth_evidence_priority_receipt_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
            "product_goal_primary_release_blocker_requirement_id": "R8_full_scope_claim_closure",
            "product_goal_primary_release_blocker_tier": "full_commercial_scope",
            "product_goal_primary_release_blocker": "full_scope_claim_closure_not_ready",
            "primary_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
            "primary_action_required_input": (
                "production_promotion_allowed;customer_facing_auto_correction_allowed;"
                "customer_facing_score_mutation_allowed;customer_facing_ranking_mutation_allowed;"
                "default_residual_mode;trained_model_checkpoint_count"
            ),
            "primary_action_status": "required",
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
            "production_ai_registry_promotion_priority_source_json": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
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
        "required_true_fields": [
            "engine_refinement_claim_evidence_priority_packet_priority_packet_ready",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_readiness_present",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_readiness_ready",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_present",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_ready",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_present",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_ready",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_present",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present",
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready",
            "product_scope_breadth_evidence_priority_packet_ready",
            "production_ai_registry_promotion_priority_packet_ready",
        ],
        "required_int_exact_fields": {
            "completion_audit_release_blocker_bottleneck_count": 2,
            "full_commercial_evidence_receipt_entry_count": 2,
            "full_commercial_evidence_receipt_operator_input_required_count": 2,
            "full_commercial_evidence_receipt_current_action_required_count": 2,
            "full_commercial_evidence_receipt_template_required_count": 2,
            "full_commercial_evidence_receipt_template_present_count": 2,
            "full_commercial_evidence_receipt_approval_token_count": 2,
            "production_ai_registry_promotion_priority_operator_input_required_count": 3,
            "production_ai_registry_promotion_priority_blocked_priority_item_count": 3,
            "production_ai_registry_promotion_priority_missing_gate_count": 3,
            "production_ai_registry_promotion_priority_observed_registry_trained_model_checkpoint_count": 1,
            "product_scope_breadth_evidence_priority_open_item_count": 15,
            "product_scope_breadth_evidence_priority_scientific_evidence_request_count": 11,
            "product_scope_breadth_evidence_priority_local_crosscheck_candidate_count": 11,
            "product_scope_breadth_evidence_priority_review_only_keep_blocked_count": 1,
            "product_scope_breadth_evidence_priority_receipt_row_count": 6,
            "product_scope_breadth_evidence_priority_receipt_blocked_row_count": 6,
            "product_scope_breadth_evidence_priority_receipt_operator_review_surface_ready_count": 6,
            "product_scope_breadth_evidence_priority_receipt_operator_review_surface_blocked_count": 0,
            "product_scope_breadth_evidence_priority_receipt_manual_field_pending_count": 36,
            "product_scope_breadth_evidence_priority_receipt_evidence_artifact_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_claim_ready_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_reviewer_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_reviewed_at_utc_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_license_ok_pending_count": 6,
            "product_scope_breadth_evidence_priority_receipt_approval_token_pending_count": 6,
            "engine_refinement_claim_evidence_priority_packet_priority_item_count": 6,
            "engine_refinement_claim_evidence_priority_packet_operator_input_required_count": 6,
            "engine_refinement_claim_evidence_priority_packet_blocked_priority_item_count": 6,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_ready_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": 1,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": 34,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": 34,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": 11,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_missing_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": 136,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": 17,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": 51,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": 0,
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": 0,
        },
        "required_text_exact_fields": {
            "engine_refinement_claim_evidence_priority_packet_source_json": (
                "runs/engine_refinement_claim_evidence_priority_packet_current.json"
            ),
            "engine_refinement_claim_evidence_priority_packet_status": (
                "blocked_engine_refinement_claim_evidence_priority_packet"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_blocker_id": (
                "public_benchmark_gate_not_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_status": (
                "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": (
                "dockq;lddt_pli;internal_deltaG"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": (
                "metric_name;target_id;pose_id;value;method;input_artifacts;"
                "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;"
                "external_engine_calls"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_receipt_csv": (
                R9_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_CSV
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                "r9_statistical_support_metric_source_template_001"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_intake_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": (
                "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            ),
            "engine_refinement_claim_evidence_priority_packet_public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": (
                "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
            ),
            "engine_refinement_claim_evidence_priority_packet_top_next_operator_step": (
                "Coordinate fetch and validation are complete "
                "(r4_ready_for_review_row_count=17, r4_blocked_row_count=0, fetch_required_row_count=0, "
                "approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD) for 17 "
                "statistical-support candidates (coordinate_validation_pass_row_count=17, "
                "metric_materialization_candidate_ready_count=17, required_input_artifacts=34/34/0, "
                "local_coordinate_present_targets=17, local_coordinate_missing_targets=0, "
                "planned_metric_source_payload_count=51); fill and review the 51 DockQ/lDDT-PLI/internal "
                "DeltaG metric source payloads, materialize them, and rerun bootstrap Spearman p05 before "
                "any R9 claim receipt or canonical intake promotion."
            ),
            "product_scope_breadth_evidence_priority_source_json": (
                "runs/product_scope_breadth_evidence_priority_packet_current.json"
            ),
            "product_scope_breadth_evidence_priority_status": (
                "product_scope_breadth_evidence_priority_packet_ready"
            ),
            "product_scope_breadth_evidence_priority_top_item_id": "AQP1.core_binder_01",
            "product_scope_breadth_evidence_priority_top_domain": "transporter",
            "product_scope_breadth_evidence_priority_top_bucket": (
                "local_crosscheck_review_present_but_exact_quant_required"
            ),
            "product_scope_breadth_evidence_priority_top_required_evidence_type": (
                "exact_transporter_target_pair_quantitative_binder_kcal"
            ),
            "product_scope_breadth_evidence_priority_receipt_status": (
                "blocked_product_scope_breadth_evidence_receipt"
            ),
            "product_scope_breadth_evidence_priority_receipt_csv": (
                "config/product_scope_breadth_evidence_receipt_current.csv"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_scope_blocker_id": (
                "direct_binding_evidence_missing"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_evidence_artifact": (
                "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_expected_evidence_status": (
                "product_scope_transporter_direct_binding_evidence_ready"
            ),
            "product_scope_breadth_evidence_priority_receipt_first_blocked_observed_evidence_status": (
                "missing"
            ),
            "product_scope_breadth_evidence_priority_receipt_most_common_row_blocker": (
                "operator_placeholders_unfilled"
            ),
            "product_scope_breadth_evidence_priority_receipt_approval_token_required": (
                "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
            ),
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
            "production_ai_registry_promotion_priority_source_json": (
                "runs/production_ai_registry_promotion_priority_packet_current.json"
            ),
            "production_ai_registry_promotion_priority_status": (
                "blocked_production_ai_registry_promotion_priority_packet"
            ),
            "production_ai_registry_promotion_priority_top_gate_id": (
                "default_residual_mode_guarded"
            ),
            "production_ai_registry_promotion_priority_top_priority_bucket": (
                "guarded_residual_mode_selection_required"
            ),
        },
    },
    {
        "artifact_id": "product_commercial_readiness_operator_packet_semantic_ready",
        "artifact_path": "runs/product_commercial_readiness_operator_packet_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_operator_packet.py",
        "required_status": "product_commercial_readiness_operator_packet_ready",
        "required_true_fields": [
            "packet_ready",
            "source_fingerprint_ready",
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready",
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready",
        ],
        "required_int_exact_fields": {
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
        },
        "required_text_exact_fields": {
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
        },
    },
    {
        "artifact_id": "product_commercial_readiness_handoff_bundle_semantic_ready",
        "artifact_path": "runs/product_commercial_readiness_handoff_bundle_current.json",
        "builder_command": "python3 tools/build_product_commercial_readiness_handoff_bundle.py",
        "required_status": "product_commercial_readiness_handoff_bundle_ready",
        "required_true_fields": [
            "handoff_bundle_ready",
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready",
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready",
        ],
        "required_int_exact_fields": {
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 51,
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 0,
        },
        "required_text_exact_fields": {
            "engine_refinement_claim_evidence_operator_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
            ),
            "engine_refinement_claim_evidence_operator_staging_apply_field_worksheet_public_benchmark_statistical_support_metric_source_templates_status": (
                "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
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


def _path_fingerprint(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path_text = _text(path_like)
    path = _resolve(path_like, root=root)
    present = path.exists()
    kind = "missing"
    size_bytes = 0
    mtime_ns = 0
    mtime_epoch = 0.0
    if present:
        if path.is_file():
            kind = "file"
        elif path.is_dir():
            kind = "directory"
        else:
            kind = "other"
        try:
            stat = path.stat()
            size_bytes = int(stat.st_size)
            mtime_ns = int(stat.st_mtime_ns)
            mtime_epoch = float(stat.st_mtime)
        except OSError:
            kind = "unreadable"
    return {
        "path": path_text,
        "present": present,
        "kind": kind,
        "sha256": _sha256_file_if_present(path_like, root=root) if kind == "file" else "",
        "size_bytes": size_bytes,
        "mtime_ns": mtime_ns,
        "mtime_utc": _iso_from_mtime(mtime_epoch),
    }


def _source_artifact_fingerprint(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    serialized = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    source_artifact_fingerprints = [_path_fingerprint(path, root=root) for path in depends_on]
    source_artifact_fingerprint_sha256 = _source_artifact_fingerprint(source_artifact_fingerprints)
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
        "source_artifact_fingerprint_sha256": source_artifact_fingerprint_sha256,
        "source_artifact_fingerprint_count": len(source_artifact_fingerprints),
        "source_artifact_file_sha256_count": sum(
            1 for item in source_artifact_fingerprints if item.get("kind") == "file" and item.get("sha256")
        ),
        "source_artifact_fingerprints": source_artifact_fingerprints,
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
