from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.product import build_product_operator_cockpit as mod


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "capabilities": tmp_path / "runs/product_capability_surface_contract_current.json",
        "goal": tmp_path / "runs/goal_readiness_rollup_current.json",
        "hbond": tmp_path / "runs/hbond_backmap_report_current.json",
        "gpcr": tmp_path / "runs/gpcr_hard_decoy_claim_unlock_audit_current.json",
        "gpcr_phase3": tmp_path / "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.json",
        "pocketmd": tmp_path / "runs/pocketmd_lite_topk_refinement_audit_current.json",
        "public": tmp_path / "runs/public_benchmark_external_receipts_audit_current.json",
        "public_attach": tmp_path / "runs/public_benchmark_receipt_attach_packet_current.json",
        "release_decision": tmp_path / "runs/goal_release_decision_gate_current.json",
        "release": tmp_path / "runs/goal_operator_action_board_current.json",
        "pm_queue": tmp_path / ".betelgeuze/pm_priority_queue_status_current.json",
        "bundle": tmp_path / "runs/ai_md_product_evidence_bundle_current.json",
        "api_customer_flow": tmp_path / "runs/api_customer_flow_release_evidence_current.json",
        "customer": tmp_path / "runs/customer_shadow_evidence_status_current.json",
        "developer_preview": tmp_path / "runs/developer_preview_final_gate_audit_current.json",
        "f2g_preflight": tmp_path / ".betelgeuze/f2g_f2h_surface_preflight.local.json",
        "f2g_recovery": (
            tmp_path / ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json"
        ),
        "enterprise": tmp_path / "runs/enterprise_on_prem_readiness_gate_current.json",
        "pr38_acceptance": tmp_path / ".betelgeuze/pr38_split_acceptance_packet_current.json",
        "pr38_matrix": tmp_path / ".betelgeuze/pr38_child_pr_verification_matrix_current.json",
    }
    _write_json(
        paths["capabilities"],
        {
            "summary": {
                "status": "product_capability_surface_contract_ready",
                "capability_count": 9,
                "ready_capability_count": 9,
                "evidence_surface_count": 5,
                "restricted_scope_claim_guard_ready": True,
                "general_platform_claim_allowed": False,
                "blocked_claim_scopes": ["general_protein_ligand_platform"],
                "claim_boundary": "capability fixture boundary",
            },
            "rows": [
                {
                    "capability_id": "molecular_structure_analysis_intake",
                    "domain": "structure_analysis",
                    "status": "ready",
                    "required": True,
                    "release_blocker": False,
                    "artifact_path": "runs/product_readiness_gate_current.json",
                    "observed": "target_id=ADRB2;family=gpcr",
                    "reason": "guarded structure-analysis intake is exposed",
                    "bundle_assembled": True,
                    "docking_results_emitted": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
                {
                    "capability_id": "general_platform_claim",
                    "domain": "claim_boundary",
                    "status": "blocked",
                    "required": False,
                    "release_blocker": True,
                    "artifact_path": "runs/product_capability_surface_contract_current.json",
                    "observed": "general_platform_claim_allowed=False",
                    "reason": "general platform wording remains locked",
                    "bundle_assembled": False,
                    "docking_results_emitted": True,
                    "claim_boundary": "general platform claim row boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
        },
    )
    _write_json(
        paths["goal"],
        {
            "summary": {
                "status": "blocked_goal_readiness",
                "blocked_lane_count": 1,
                "operator_or_external_pending_lane_count": 3,
                "goal_completion_audit_goal_complete": False,
                "release_complete_lane_ready": False,
                "claim_boundary": "goal readiness fixture boundary",
            },
            "rows": [
                {
                    "lane_id": "commercial_product_execution",
                    "lane_status": "operator_approval_pending",
                    "artifact_path": (
                        "runs/product_readiness_gate_current.json;"
                        "runs/product_execution_preflight_current.json"
                    ),
                    "artifact_present": True,
                    "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
                    "blocker_count": 0,
                    "observed_status": "product_handoff_ready;product_execution_preflight_ready",
                    "next_required_step": (
                        "Pilot packet is ready for final human review and restricted customer handoff."
                    ),
                    "reclaim_size_gb": 0,
                    "action_executed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                },
                {
                    "lane_id": "product_ai_architecture",
                    "lane_status": "evidence_ready",
                    "artifact_path": (
                        "runs/product_ai_architecture_gap_closure_current.json;"
                        "runs/product_ai_architecture_execution_backlog_current.json"
                    ),
                    "artifact_present": True,
                    "approval_token_required": "",
                    "blocker_count": 0,
                    "observed_status": (
                        "blocked_product_ai_architecture_gap_closure;"
                        "release_blocking_work_item_count=0"
                    ),
                    "next_required_step": (
                        "Keep optional AI architecture gaps deferred until promotion decision."
                    ),
                    "reclaim_size_gb": 0,
                    "claim_boundary": "goal optional architecture row boundary",
                    "action_executed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
        },
    )
    _write_json(
        paths["hbond"],
        {
            "status": "hbond_backmap_report_ready",
            "summary": {
                "candidate_count": 2,
                "claim_safe_count": 1,
                "total_donor_sites": 2,
                "total_acceptor_sites": 1,
            },
            "rows": [
                {
                    "entry_id": "ADRB2::LIG-1",
                    "evidence_tier": "claim_safe",
                    "claim_safe": True,
                    "backmap_status": "ok",
                    "mapping_source": "rdkit_etkdg",
                    "site_count": 2,
                    "mapped_site_count": 2,
                    "donor_count": 1,
                    "acceptor_count": 1,
                    "max_onsps_sites": 4,
                    "polar_site_elements": ["N", "O"],
                    "hbond_angle_score": 0.75,
                    "two_bead_vs_four_bead_delta": None,
                    "reason_code": "",
                    "reason_detail": "",
                    "report_version": "hbond_backmap_report_v1",
                    "claim_boundary": "hbond interpretability only",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {"entry_id": "ADRB2::LIG-2", "claim_safe": False},
            ],
        },
    )
    _write_json(
        paths["gpcr"],
        {
            "summary": {
                "status": "gpcr_hard_decoy_claim_unlock_metric_evidence_ready_promotion_locked",
                "hard_decoy_metric_claim_unlock_ready": True,
                "preregistered_ranking_pr_auc_ci_low": 0.5597832604695224,
                "preregistered_top20_hit_rate": 1.0,
                "preregistered_decoys_above_positive_count": 0,
                "claim_promotion_allowed": False,
                "router_claim_allowed": False,
                "platform_claim_allowed": False,
                "promotion_blocker_count": 2,
                "promotion_work_order_row_count": 2,
                "promotion_work_order_lane_count": 2,
                "promotion_work_order_primary_blocker": "broad_scope:formal_broad_claim_review_not_approved",
                "promotion_blockers": [
                    "broad_scope:formal_broad_claim_review_not_approved",
                    "scorer_router_promotion_gate_not_ready",
                ],
            },
            "promotion_work_order_rows": [
                {
                    "lane_id": "active_scorer",
                    "blocker": "active_scorer:operational_gate_refresh_not_complete",
                    "required_action": (
                        "Refresh the active scorer operational gate and keep broad GPCR "
                        "promotion locked."
                    ),
                    "source_artifact": (
                        "runs/gpcr_active_scorer_promotion_decision_packet_current.json"
                    ),
                    "claim_boundary": "GPCR promotion work order only; no broad claim promotion.",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["gpcr_phase3"],
        {
            "summary": {
                "status": "gpcr_hard_decoy_phase3_closure_evidence_ready",
                "phase3_closure_evidence_ready": True,
                "claim_unlock_phase3_exit_metric_conditions_ready": True,
                "claim_unlock_broad_promotion_remains_locked": True,
                "effective_phase3_ranking_pr_auc_ci_low": 0.5597832604,
                "effective_phase3_top20_hit_rate": 1.0,
                "effective_phase3_decoys_above_positive_total": 0,
                "effective_phase3_metric_source": "claim_unlock_audit",
                "claim_unlock_promotion_blockers": [
                    "broad_scope:formal_broad_claim_review_not_approved",
                    "scorer_router_promotion_gate_not_ready",
                ],
                "next_required_step": "Keep broad GPCR promotion locked.",
            }
        },
    )
    _write_json(
        paths["pocketmd"],
        {
            "summary": {
                "status": "pocketmd_lite_topk_refinement_audit_ready",
                "candidate_count": 5,
                "green_row_count": 5,
                "yellow_row_count": 0,
                "red_row_count": 0,
                "abstain_row_count": 0,
                "claim_grade_metric_ready_count": 5,
                "claim_grade_refinement_evidence_ready": True,
                "claim_grade_report_evidence_ready": False,
                "claim_grade_fill_preview_evidence_ready": True,
                "green_band_condition_text": (
                    "green requires local-min RMSD, hbond/contact persistence, and clash relief."
                ),
                "claim_promotion_allowed": False,
            },
            "rows": [
                {
                    "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
                    "band": "green",
                    "uncertainty_posture": "green_low_uncertainty",
                    "uncertainty_score": 0.23,
                    "claim_grade_metric_ready": True,
                    "claim_safe": True,
                    "selected_for_refine": True,
                    "local_min_ligand_rmsd_a": 1.29,
                    "local_min_survived": True,
                    "hbond_persistence": 0.8,
                    "contact_persistence": 1.0,
                    "initial_clash_count": 57,
                    "clash_count": 0,
                    "clash_relief_count": 57,
                    "claim_grade_missing_metrics": [],
                    "blockers": [],
                    "trajectory_probe_status": "pocketmd_lite_metric_collection_probe_ready",
                    "candidate_metric_fill_status": "filled_from_claim_grade_probe",
                    "recommended_next_local_action": "review_green_band_metrics",
                    "candidate_csv_update_allowed": True,
                    "refinement_execution_enabled": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "entry_id": "ADRB2_GPCR_BLIND:timolol",
                    "claim_grade_metric_ready": True,
                    "local_min_ligand_rmsd_a": 0.86,
                    "hbond_persistence": 1.0,
                    "contact_persistence": 0.9,
                    "initial_clash_count": 22,
                    "clash_count": 1,
                    "clash_relief_count": 21,
                },
            ],
        },
    )
    _write_json(
        paths["public"],
        {
            "summary": {
                "status": "blocked_public_benchmark_external_receipts_audit",
                "external_benchmark_receipts_ready": False,
                "ready_step_count": 5,
                "step_count": 7,
                "blocked_step_count": 2,
                "receipt_blocked_row_count": 51,
                "vina_gnina_comparison_adapter_score_evidence_ready": False,
                "vina_gnina_pending_field_count": 192,
                "comparison_adapter_same_input_row_count_match": False,
                "primary_blocker_id": "vina_gnina_same_input_comparison",
                "primary_blocker": "vina_gnina_same_input_score_evidence_missing",
                "primary_blocker_next_required_step": (
                    "Attach operator-provided Vina/GNINA scores for the same subset rows, then rerun the adapter."
                ),
                "vina_gnina_score_template_csv": (
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "vina_gnina_score_template_receipt_json": (
                    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                ),
                "vina_gnina_adapter_command_after_fill": (
                    "python3 tools/build_pdbbind_casf_pose_affinity_results.py --comparison-scores-csv "
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "blockers": [
                    "vina_gnina_same_input_comparison:vina_gnina_same_input_score_evidence_missing",
                    "benchmark_receipt_attach:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "claim_promotion_allowed": False,
            },
            "rows": [
                {
                    "step_id": "vina_gnina_same_input_comparison",
                    "status": "blocked",
                    "ready": False,
                    "evidence_artifact": (
                        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                    ),
                    "primary_metric": "score_rows=0/16",
                    "secondary_metric": "pending_fields=192",
                    "blocker": "vina_gnina_same_input_score_evidence_missing",
                    "next_required_step": (
                        "Fill every score-template row with same-input Vina/GNINA scores."
                    ),
                    "claim_boundary": "public benchmark audit boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["public_attach"],
        {
            "summary": {
                "status": "blocked_public_benchmark_receipt_attach_packet",
                "receipt_attach_packet_ready": False,
                "external_benchmark_receipts_ready": False,
                "blocker_count": 2,
                "primary_blocker_id": "vina_gnina_same_input_scores",
                "primary_blocker": "vina_gnina_same_input_score_evidence_missing",
                "blockers": [
                    "vina_gnina_same_input_scores:vina_gnina_same_input_score_evidence_missing",
                    "metric_source_receipt_rows:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "vina_gnina_score_template_csv": (
                    "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                ),
                "vina_gnina_score_template_receipt_json": (
                    "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                ),
                "metric_source_receipt_csv": (
                    "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
                ),
                "vina_gnina_score_value_pending_count": 32,
                "metric_source_receipt_manual_field_pending_count": 510,
                "metric_source_receipt_approval_token_pending_count": 51,
                "field_work_order_row_count": 22,
                "field_work_order_pending_field_count": 702,
                "field_work_order_primary_field_name": "approval_token",
                "field_work_order_primary_lane_id": "vina_gnina_same_input_scores",
                "field_work_order_primary_pending_row_count": 16,
                "field_work_order_primary_required_value": (
                    "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                ),
                "field_work_order_primary_required_action": (
                    "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                    "after operator review."
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
                "next_required_step": "Fill the receipt attach packet rows before rerunning the benchmark audit.",
            },
            "rows": [
                {
                    "lane_id": "vina_gnina_same_input_scores",
                    "status": "blocked",
                    "ready": False,
                    "blocker": "vina_gnina_same_input_score_evidence_missing",
                    "source_artifact": (
                        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                    ),
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
                    "next_required_step": (
                        "Fill every Vina/GNINA same-input score template row."
                    ),
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
                    "required_value": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
                    ),
                    "required_action": (
                        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                        "after operator review."
                    ),
                    "approval_token_required": (
                        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
                    ),
                    "operator_csv": (
                        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
                    ),
                    "source_artifact": (
                        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
                    ),
                    "claim_boundary": "same-input Vina/GNINA score receipt only",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["release_decision"],
        {
            "summary": {
                "status": "blocked_goal_release_decision",
                "release_allowed": False,
                "restricted_release_allowed": False,
                "blocker_count": 1,
                "next_required_step": "Clear third-party license review gate before release.",
                "claim_boundary": "release decision fixture boundary",
            },
            "rows": [
                {
                    "lane_id": "commercial_product_release",
                    "check": "third_party_license_review_gate_recorded",
                    "status": "fail",
                    "release_blocker": True,
                    "artifact_path": "runs/third_party_license_review_gate_current.json",
                    "required": "third-party license review gate ready for JSZip",
                    "observed": "third_party_license_review_gate_ready;review_csv_present=false",
                    "reason": (
                        "The final release decision must keep JSZip dual-license "
                        "redistribution review visible as an operator/legal boundary."
                    ),
                    "action_executed": True,
                    "delete_executed": True,
                    "outbound_email_enabled": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["release"],
        {
            "summary": {
                "status": "operator_actions_required",
                "goal_release_allowed": True,
                "goal_release_blocker_count": 4,
                "primary_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
                "primary_action_recommended_action": "Complete the guarded production AI registry promotion receipt.",
                "goal_release_decision_gate_status": "blocked_goal_release_decision",
            },
            "rows": [
                {
                    "lane_id": "product_ai_production",
                    "action_type": "complete_residual_registry_guarded_promotion",
                    "status": "required",
                    "priority": 0,
                    "approval_token": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
                    "required_input": "production_promotion_allowed;default_residual_mode",
                    "artifact_path": (
                        "runs/product_goal_completion_audit_current.json;"
                        "runs/residual_model_registry_current.json"
                    ),
                    "command": (
                        "python3 tools/build_residual_model_registry.py && "
                        "python3 tools/build_product_production_ai_checkpoint_readiness.py"
                    ),
                    "reason": "registry promotion gates are not satisfied",
                    "recommended_action": (
                        "Complete the guarded production AI registry promotion receipt."
                    ),
                    "operator_completion_artifact_id": (
                        "residual_model_registry_guarded_promotion"
                    ),
                    "operator_completion_completion_rule": (
                        "registry_promotion_missing_gate_count=0"
                    ),
                    "operator_completion_next_action": (
                        "Complete the guarded production AI registry promotion receipt."
                    ),
                    "operator_completion_required_fields_or_columns": (
                        "production_promotion_allowed;default_residual_mode"
                    ),
                    "parallelizable_with_primary_action": True,
                    "parallel_lane_precondition": "claim promotion remains locked",
                    "action_executed": True,
                    "delete_executed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                    "claim_boundary": "unsafe fixture value should be preserved as text only",
                }
            ],
        },
    )
    _write_json(
        paths["pm_queue"],
        {
            "summary": {
                "status": "blocked_pm_priority_queue",
                "ready_item_count": 3,
                "blocked_item_count": 5,
                "first_blocked_item_id": "2",
                "next_required_step": (
                    "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                ),
            },
            "rows": [
                {
                    "item_id": "1",
                    "status": "source_of_truth_refresh_synced",
                    "ready": True,
                    "blocker": "",
                    "next_action": "Source-of-truth snapshots agree.",
                },
                {
                    "item_id": "2",
                    "status": "blocked_f2g_f2h_surface_preflight",
                    "ready": False,
                    "blocker": "f2g_authoritative_surfaces_missing",
                    "next_action": (
                        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                    ),
                },
            ],
        },
    )
    _write_json(
        paths["bundle"],
        {
            "summary": {
                "status": "ai_md_product_evidence_bundle_ready",
                "bundle_export_ready": True,
                "bundle_tar_exists": True,
                "bundle_tar_member_count": 14,
                "bundle_validation_pass": True,
                "release_claim_ready": False,
                "claim_boundary": "bundle fixture boundary",
            },
            "rows": [
                {
                    "artifact_id": "ai_md_engine_kpi_report_json",
                    "role": "local_pc_runtime_report",
                    "artifact_path": "runs/ai_md_engine_kpi_report_current.json",
                    "bundle_arcname": "runs/ai_md_engine_kpi_report_current.json",
                    "required": True,
                    "exists": True,
                    "missing": False,
                    "included_in_bundle": True,
                    "release_blocker": False,
                    "sha256": "abc123",
                    "size_bytes": 143772,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "artifact_id": "optional_runtime_plot",
                    "role": "runtime_plot",
                    "artifact_path": "runs/ai_md_runtime_scaling_plot_current.svg",
                    "bundle_arcname": "runs/ai_md_runtime_scaling_plot_current.svg",
                    "required": False,
                    "exists": True,
                    "missing": False,
                    "included_in_bundle": True,
                    "release_blocker": False,
                    "sha256": "def456",
                    "size_bytes": 2048,
                    "claim_boundary": "plot artifact row boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
        },
    )
    _write_json(
        paths["api_customer_flow"],
        {
            "summary": {
                "status": "api_customer_flow_release_evidence_ready",
                "pass_count": 6,
                "blocker_count": 0,
                "formal_release_evidence_ready": True,
                "clean_install_flow_ready": True,
                "restricted_unattended_runtime_ready": True,
                "result_manifest_signature_verified": True,
                "bundle_validation_ready": True,
                "tier_alpha_smoke_status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "tier_alpha_runner_execution_ok": True,
                "claim_boundary": "api customer flow fixture boundary",
            },
            "rows": [
                {
                    "check_id": "tier_alpha_smoke_live_job_ready",
                    "status": "pass",
                    "release_blocker": False,
                    "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
                    "required": "tier alpha smoke pass",
                    "observed": "runner_execution_ok=True",
                    "reason": "prove the validated runner drained a restricted job",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "check_id": "bundle_validation_ready",
                    "status": "pass",
                    "release_blocker": False,
                    "artifact_path": (
                        "runs/product_bundle_contract_current.json;"
                        "runs/product_delivery_evidence_contract_current.json"
                    ),
                    "required": "bundle validation passed",
                    "observed": "bundle_validation=True;delivery_claim=True",
                    "reason": "customer flow terminates in validated bundle gates",
                    "claim_boundary": "bundle validation row boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
        },
    )
    _write_json(
        paths["customer"],
        {
            "summary": {
                "status": "blocked_customer_shadow_evidence_status",
                "customer_shadow_intake_schema_ready": True,
                "customer_shadow_minimum_met": False,
                "real_customer_shadow_row_count": 1,
                "completed_customer_shadow_case_count": 0,
                "required_completed_customer_shadow_case_count": 3,
                "missing_completed_customer_shadow_case_count": 3,
                "customer_raw_data_stored_in_repo": False,
                "customer_retained_raw_data_count": 1,
                "redistribution_allowed_false_count": 1,
                "redistribution_allowed_required_value": False,
                "anonymized_result_summary_count": 1,
                "reviewer_signoff_count": 0,
                "invalid_row_count": 0,
                "mock_fixture_row_count": 0,
                "required_column_count": 12,
                "blocker_count": 2,
                "customer_shadow_work_order_ready": False,
                "customer_shadow_work_order_row_count": 3,
                "customer_shadow_work_order_primary_case_slot_id": "customer_shadow_case_1",
                "customer_shadow_work_order_primary_required_action": (
                    "Add one reviewed real customer-shadow metadata row."
                ),
                "customer_shadow_work_order_primary_operator_csv": (
                    "config/customer_shadow_evidence_intake_template.csv"
                ),
                "customer_shadow_work_order_primary_required_row_kind": "customer_shadow",
                "customer_shadow_work_order_primary_required_raw_data_custody": "customer_retained",
                "customer_shadow_work_order_primary_required_customer_retained_raw_data": True,
                "customer_shadow_work_order_primary_required_redistribution_allowed": False,
                "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": False,
                "customer_shadow_work_order_primary_required_derived_metadata_fields": [
                    "artifact_fingerprint",
                    "case_domain",
                    "input_size_class",
                    "result_metric_summary",
                    "runner_profile",
                ],
                "customer_shadow_work_order_primary_required_reviewer_signoff_status": "approved",
                "customer_shadow_work_order_primary_required_source_artifact_fingerprint": "sha256",
                "paid_pilot_evidence_ready": False,
                "paid_pilot_claim_allowed": False,
            },
            "rows": [
                {
                    "case_id": "customer_shadow_case_0",
                    "case_slot_id": "customer_shadow_case_0",
                    "row_kind": "customer_shadow",
                    "case_domain": "gpcr",
                    "raw_data_custody": "customer_retained",
                    "customer_retained_raw_data": True,
                    "raw_data_stored_in_repo": False,
                    "redistribution_allowed": False,
                    "anonymized_result_summary": "Aggregate-only restricted workflow summary.",
                    "reviewer_id": "reviewer-1",
                    "reviewer_signoff_status": "pending",
                    "reviewed_at_utc": "",
                    "source_artifact_fingerprint": "sha256:source",
                    "artifact_fingerprint": "sha256:artifact",
                    "derived_metadata_fields": [
                        "artifact_fingerprint",
                        "case_domain",
                        "input_size_class",
                        "result_metric_summary",
                        "runner_profile",
                    ],
                    "claim_boundary": "customer shadow fixture boundary",
                    "raw_data_ingested": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
            "customer_shadow_work_order_rows": [
                {
                    "work_order_id": "customer_shadow_case_slot_1",
                    "case_slot_id": "customer_shadow_case_1",
                    "status": "missing_customer_shadow_evidence",
                    "required_row_kind": "customer_shadow",
                    "operator_csv": "config/customer_shadow_evidence_intake_template.csv",
                    "required_action": "Add one reviewed real customer-shadow metadata row.",
                    "required_raw_data_custody": "customer_retained",
                    "required_customer_retained_raw_data": True,
                    "required_redistribution_allowed": False,
                    "required_raw_data_stored_in_repo": False,
                    "required_derived_metadata_fields": [
                        "artifact_fingerprint",
                        "case_domain",
                        "input_size_class",
                        "result_metric_summary",
                        "runner_profile",
                    ],
                    "required_reviewer_signoff_status": "approved",
                    "required_source_artifact_fingerprint": "sha256",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["developer_preview"],
        {
            "summary": {
                "status": "blocked_developer_preview_final_gate_audit",
                "developer_preview_clean_baseline_ready": False,
                "gate_count": 6,
                "ready_gate_count": 3,
                "blocked_gate_count": 3,
                "receipt_work_order_row_count": 29,
                "receipt_blocker_count": 12,
                "receipt_work_order_source_blocker_count": 7,
                "receipt_work_order_primary_gate_id": "benchmark_results_clean_checkout_regenerated",
                "receipt_work_order_primary_receipt_artifact": (
                    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                ),
                "receipt_work_order_primary_required_receipt_status": (
                    "developer_preview_clean_checkout_benchmark_receipt_ready"
                ),
                "receipt_work_order_primary_required_true_fields": [
                    "clean_checkout_benchmark_regenerated",
                    "ai_verify_passed",
                    "reviewed_receipt_attached",
                ],
                "receipt_work_order_primary_required_zero_fields": [
                    "blocker_count",
                    "failed_count",
                ],
                "receipt_work_order_primary_source_blocker_gate_id": (
                    "benchmark_results_clean_checkout_regenerated"
                ),
                "receipt_work_order_primary_source_blocker_receipt_artifact": (
                    ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                ),
                "receipt_work_order_primary_source_blocker": (
                    ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
                ),
                "receipt_work_order_primary_source_blocker_required_action": (
                    "Attach the missing source evidence required by the receipt."
                ),
                "primary_blocker_id": "benchmark_results_clean_checkout_regenerated",
                "next_required_step": "Attach the clean-checkout benchmark receipt.",
                "blockers": [
                    "benchmark_results_clean_checkout_regenerated:.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                ],
                "claim_boundary": "developer preview boundary",
            },
            "rows": [
                {
                    "gate_id": "benchmark_results_clean_checkout_regenerated",
                    "priority": "A",
                    "status": "blocked_developer_preview_gate",
                    "ready": False,
                    "receipt_artifacts": (
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                    ),
                    "required_receipt_count": 1,
                    "present_receipt_count": 1,
                    "present_blocked_receipt_count": 1,
                    "receipt_blocker_count": 5,
                    "primary_metric": "required_ready=false; review_ready=false",
                    "secondary_metric": "present_receipts=1; required_receipts=1",
                    "blocker": (
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                        "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                    ),
                    "blockers": [
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                        "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                    ],
                    "receipt_blockers": [
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                        "clean_checkout_benchmark_regenerated_not_true"
                    ],
                    "next_required_step": "Attach the clean-checkout benchmark receipt.",
                    "claim_boundary": "developer preview boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "gate_id": "silent_import_loss_zero",
                    "priority": "A",
                    "status": "developer_preview_gate_ready",
                    "ready": True,
                    "receipt_artifacts": (
                        ".betelgeuze/developer_preview_silent_import_receipt.json"
                    ),
                    "required_receipt_count": 1,
                    "present_receipt_count": 1,
                    "present_blocked_receipt_count": 0,
                    "receipt_blocker_count": 0,
                    "primary_metric": "silent_import_loss=0",
                    "secondary_metric": "present_receipts=1; required_receipts=1",
                    "blocker": "",
                    "blockers": [],
                    "receipt_blockers": [],
                    "next_required_step": "",
                    "claim_boundary": "developer preview boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
            ],
            "receipt_work_order_rows": [
                {
                    "gate_id": "benchmark_results_clean_checkout_regenerated",
                    "priority": "A",
                    "receipt_artifact": (
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
                    ),
                    "receipt_kind": "required",
                    "blocker_scope": "receipt_contract",
                    "blocker": (
                        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                        "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                    ),
                    "blocker_detail": (
                        "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                    ),
                    "required_action": "Rebuild the receipt after clearing its source blockers.",
                    "next_required_step": "Attach the clean-checkout benchmark receipt.",
                    "required_receipt_status": (
                        "developer_preview_clean_checkout_benchmark_receipt_ready"
                    ),
                    "required_true_field_count": 3,
                    "required_true_fields": [
                        "clean_checkout_benchmark_regenerated",
                        "ai_verify_passed",
                        "reviewed_receipt_attached",
                    ],
                    "required_zero_field_count": 2,
                    "required_zero_fields": ["blocker_count", "failed_count"],
                    "claim_boundary": "developer preview boundary",
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    _write_json(
        paths["f2g_preflight"],
        {
            "summary": {
                "status": "blocked_f2g_f2h_surface_preflight",
                "blocker_count": 8,
                "blockers": [
                    "implementation_phase1_dir_missing",
                    "real_mgt_input_surface_missing",
                    "f2h_blocked_until_f2g_audit",
                ],
                "f2g_audit_ready": False,
                "f2h_continuation_allowed": False,
                "g1_promotion_allowed": False,
                "next_required_step": "Restore the missing F2/G1 real-MGT surfaces.",
                "claim_boundary": "f2g preflight boundary",
            }
        },
    )
    _write_json(
        paths["f2g_recovery"],
        {
            "summary": {
                "status": "f2g_f2h_authoritative_surface_recovery_packet_ready",
                "preflight_status": "blocked_f2g_f2h_surface_preflight",
                "preflight_blocker_count": 8,
                "recovery_required": True,
                "recovery_item_count": 8,
                "blocked_recovery_item_count": 8,
                "placeholder_surface_creation_allowed": False,
                "surface_restore_executed": False,
                "g1_promotion_allowed": False,
                "next_required_step": (
                    "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                ),
                "claim_boundary": "f2g recovery boundary",
            },
            "rows": [
                {
                    "recovery_item_id": "restore_implementation_phase1_tree",
                    "preflight_check_id": "implementation_phase1_dir",
                    "status": "fail",
                    "required_surface": "implementation/phase1",
                    "observed": "missing",
                    "blocker": "implementation_phase1_dir_missing",
                    "operator_action": (
                        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                    ),
                    "acceptance_rule": (
                        "Directory exists in the checkout and is the reviewed implementation tree."
                    ),
                    "authoritative_source_hint": "Original F2/G1 implementation branch.",
                    "prohibited_actions": "do_not_create_placeholder_json;do_not_promote_g1",
                    "audit_executed": True,
                    "continuation_executed": True,
                    "surface_restore_executed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                },
                {
                    "recovery_item_id": "restore_real_mgt_input_surface",
                    "preflight_check_id": "real_mgt_input_surface",
                    "status": "fail",
                    "required_surface": "real-MGT model/input packet",
                    "blocker": "real_mgt_input_surface_missing",
                    "operator_action": "Restore the reviewed real-MGT model/input packet.",
                },
            ],
        },
    )
    _write_json(
        paths["enterprise"],
        {
            "summary": {
                "status": "blocked_enterprise_on_prem_readiness_gate",
                "enterprise_on_prem_ready": False,
                "control_count": 10,
                "ready_control_count": 4,
                "blocked_control_count": 6,
                "primary_blocker_id": "oidc_rbac_tenant_isolation",
                "primary_blocker": "oidc_rbac_claim_grade_evidence_missing",
                "next_required_step": (
                    "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
                ),
                "oidc_rbac_ready": False,
                "object_storage_ready": False,
                "gpu_scheduler_ready": False,
                "audit_provenance_metrics_tracing_ready": False,
                "license_control_ready": True,
                "support_bundle_recovery_drill_ready": False,
                "rollback_retry_idempotency_ready": True,
                "claim_boundary": "enterprise boundary",
            },
            "rows": [
                {
                    "control_id": "oidc_rbac_tenant_isolation",
                    "title": "OIDC/RBAC and tenant isolation",
                    "status": "blocked_oidc_rbac_not_verified",
                    "ready": False,
                    "blocker": "oidc_rbac_claim_grade_evidence_missing",
                    "next_action": (
                        "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
                    ),
                    "evidence": (
                        "auth_ready=true;tenant_isolation_ready=true;oidc_ready=false;rbac_ready=false"
                    ),
                    "evidence_artifacts": [
                        "runs/product_security_deployment_contract_current.json"
                    ],
                    "claim_allowed": True,
                    "execution_enabled": True,
                    "external_state_mutated": True,
                    "claim_promotion_allowed": True,
                }
            ],
        },
    )
    pr38_locks = [
        "paid_pilot_wording_allowed=false",
        "public_benchmark_claim_allowed=false",
        "gpcr_broad_claim_allowed=false",
        "pocketmd_lite_claim_allowed=false",
        "f2g_f2h_placeholder_surface_creation_allowed=false",
        "f2h_continuation_allowed=false",
    ]
    _write_json(
        paths["pr38_acceptance"],
        {
            "summary": {
                "status": "pr38_split_acceptance_packet_ready",
                "split_acceptance_ready": True,
                "child_pr_count": 5,
                "ready_child_pr_count": 5,
                "blocked_child_pr_count": 0,
                "blocked_slice_ids": [],
                "hunk_split_review_required_count": 7,
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_packet": False,
                "patches_applied": False,
                "branches_created": False,
                "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                "product_mode_expected_fail_closed_blockers": [],
                "product_mode_claim_boundary_expected_locks": pr38_locks,
                "next_required_step": (
                    "Request explicit human approval for branch/commit work, then apply checked patches in order."
                ),
                "claim_boundary": "pr38 split acceptance boundary",
            }
        },
    )
    _write_json(
        paths["pr38_matrix"],
        {
            "summary": {
                "status": "pr38_child_pr_verification_matrix_ready",
                "verification_matrix_ready": True,
                "child_pr_count": 5,
                "ready_child_pr_count": 5,
                "blocked_child_pr_count": 0,
                "blocked_slice_ids": [],
                "focused_test_required_count": 5,
                "ai_verify_required_count": 5,
                "product_mode_required_count": 5,
                "hunk_split_review_required_count": 2,
                "claim_boundary_review_required_count": 5,
                "paid_pilot_wording_allowed": False,
                "branch_commit_work_allowed_by_this_matrix": False,
                "patches_applied": False,
                "branches_created": False,
                "product_mode_expected_result": "pass_product_smoke_claim_boundaries_locked",
                "product_mode_expected_fail_closed_blockers": [],
                "product_mode_claim_boundary_expected_locks": pr38_locks,
                "next_required_step": (
                    "After explicit human approval for branch/commit work, run each row's focused test command and ai-verify."
                ),
                "claim_boundary": "pr38 child verification boundary",
            },
            "rows": [
                {
                    "sequence": 1,
                    "slice_id": "f2g_f2h_preflight",
                    "changed_file_count": 5,
                    "integration_touchpoint_count": 0,
                    "focused_test_required": True,
                    "focused_test_command": (
                        "python3 -m pytest -q "
                        "tests/unit/test_build_f2g_f2h_authoritative_surface_recovery_packet.py"
                    ),
                    "ai_verify_required": True,
                    "ai_verify_command": "./scripts/ai-verify.sh",
                    "product_mode_required": True,
                    "product_mode_command": "AI_VERIFY_MODE=product ./scripts/ai-verify.sh",
                    "claim_boundary_review_required": True,
                    "child_pr_verification_matrix_ready": True,
                    "verification_blockers": [],
                    "paid_pilot_wording_allowed": False,
                    "branch_commit_work_allowed_by_this_matrix": False,
                    "execution_enabled": False,
                    "external_state_mutated": False,
                }
            ],
        },
    )
    return paths


def _build_payload(tmp_path: Path) -> dict:
    paths = _write_inputs(tmp_path)
    return mod.build_product_operator_cockpit(
        capabilities_json=paths["capabilities"],
        goal_readiness_json=paths["goal"],
        hbond_json=paths["hbond"],
        gpcr_json=paths["gpcr"],
        gpcr_phase3_closure_json=paths["gpcr_phase3"],
        pocketmd_json=paths["pocketmd"],
        public_benchmark_json=paths["public"],
        public_benchmark_receipt_attach_packet_json=paths["public_attach"],
        goal_release_decision_json=paths["release_decision"],
        release_actions_json=paths["release"],
        pm_priority_queue_json=paths["pm_queue"],
        evidence_bundle_json=paths["bundle"],
        api_customer_flow_json=paths["api_customer_flow"],
        customer_shadow_json=paths["customer"],
        developer_preview_json=paths["developer_preview"],
        f2g_f2h_preflight_json=paths["f2g_preflight"],
        f2g_f2h_recovery_json=paths["f2g_recovery"],
        enterprise_on_prem_json=paths["enterprise"],
        pr38_split_acceptance_json=paths["pr38_acceptance"],
        pr38_child_pr_verification_matrix_json=paths["pr38_matrix"],
        root=tmp_path,
    )


def test_product_operator_cockpit_surfaces_phase8_panels_and_locks_claims(tmp_path: Path) -> None:
    payload = _build_payload(tmp_path)
    summary = payload["summary"]
    panels = {row["panel_id"]: row for row in payload["rows"]}
    claims = {row["claim_id"]: row for row in payload["claim_matrix"]}

    assert summary["status"] == "product_operator_cockpit_ready_claims_blocked"
    assert summary["phase8_surface_ready"] is True
    assert summary["required_phase8_panel_count"] == 9
    assert summary["observed_phase8_panel_count"] == 14
    assert summary["missing_required_phase8_panel_count"] == 0
    assert summary["paid_pilot_wording_allowed"] is False
    assert summary["allowed_claim_count"] == 5
    assert summary["disallowed_claim_count"] == 6
    assert summary["allowed_claim_ids"] == [
        "operator_cockpit_surface",
        "restricted_scope_claim_guard",
        "gpcr_hard_decoy_metric_review",
        "pocketmd_lite_refinement_evidence",
        "evidence_bundle_export",
    ]
    assert summary["disallowed_claim_ids"] == [
        "paid_pilot_wording",
        "general_platform_claim",
        "broad_gpcr_claim",
        "pocketmd_lite_customer_claim",
        "public_benchmark_claim",
        "enterprise_on_prem_platform_claim",
    ]
    assert summary["allowed_claim_text"] == (
        "operator_cockpit_surface; restricted_scope_claim_guard; "
        "gpcr_hard_decoy_metric_review; pocketmd_lite_refinement_evidence; "
        "evidence_bundle_export"
    )
    assert summary["disallowed_claim_text"] == (
        "paid_pilot_wording; general_platform_claim; broad_gpcr_claim; "
        "pocketmd_lite_customer_claim; public_benchmark_claim; "
        "enterprise_on_prem_platform_claim"
    )
    assert claims["paid_pilot_wording"]["claim_text"] == (
        "Paid pilot wording is not allowed until release and customer-shadow "
        "evidence gates pass."
    )
    assert claims["general_platform_claim"]["claim_text"] == (
        "General protein-ligand platform claim is not allowed."
    )
    assert claims["broad_gpcr_claim"]["claim_text"] == (
        "Broad GPCR/router/scorer claim is not allowed."
    )
    assert claims["pocketmd_lite_customer_claim"]["claim_text"] == (
        "PocketMD Lite customer-facing claim-grade reporting is not allowed."
    )
    assert claims["public_benchmark_claim"]["claim_text"] == (
        "Public benchmark claim-grade support is not allowed."
    )
    assert claims["enterprise_on_prem_platform_claim"]["claim_text"] == (
        "Enterprise/on-prem platform claim is not allowed."
    )
    assert all(
        " is allowed" not in claims[claim_id]["claim_text"]
        for claim_id in summary["disallowed_claim_ids"]
    )
    assert summary["general_platform_claim_allowed"] is False
    assert summary["product_capability_row_count"] == 2
    assert summary["product_capability_blocker_row_count"] == 1
    assert summary["product_capability_rows"] == [
        {
            "capability_id": "molecular_structure_analysis_intake",
            "domain": "structure_analysis",
            "status": "ready",
            "required": True,
            "release_blocker": False,
            "artifact_path": "runs/product_readiness_gate_current.json",
            "observed": "target_id=ADRB2;family=gpcr",
            "reason": "guarded structure-analysis intake is exposed",
            "bundle_assembled": True,
            "docking_results_emitted": False,
            "claim_boundary": "capability fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "capability_id": "general_platform_claim",
            "domain": "claim_boundary",
            "status": "blocked",
            "required": False,
            "release_blocker": True,
            "artifact_path": "runs/product_capability_surface_contract_current.json",
            "observed": "general_platform_claim_allowed=False",
            "reason": "general platform wording remains locked",
            "bundle_assembled": False,
            "docking_results_emitted": False,
            "claim_boundary": "general platform claim row boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["goal_readiness_row_count"] == 2
    assert summary["goal_readiness_action_required_row_count"] == 1
    assert summary["goal_readiness_rows"] == [
        {
            "lane_id": "commercial_product_execution",
            "lane_status": "operator_approval_pending",
            "artifact_path": (
                "runs/product_readiness_gate_current.json;"
                "runs/product_execution_preflight_current.json"
            ),
            "artifact_present": True,
            "approval_token_required": "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "blocker_count": 0,
            "observed_status": "product_handoff_ready;product_execution_preflight_ready",
            "next_required_step": (
                "Pilot packet is ready for final human review and restricted customer handoff."
            ),
            "reclaim_size_gb": 0.0,
            "claim_boundary": "goal readiness fixture boundary",
            "action_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "lane_id": "product_ai_architecture",
            "lane_status": "evidence_ready",
            "artifact_path": (
                "runs/product_ai_architecture_gap_closure_current.json;"
                "runs/product_ai_architecture_execution_backlog_current.json"
            ),
            "artifact_present": True,
            "approval_token_required": "",
            "blocker_count": 0,
            "observed_status": (
                "blocked_product_ai_architecture_gap_closure;"
                "release_blocking_work_item_count=0"
            ),
            "next_required_step": (
                "Keep optional AI architecture gaps deferred until promotion decision."
            ),
            "reclaim_size_gb": 0.0,
            "claim_boundary": "goal optional architecture row boundary",
            "action_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["hbond_backmap_candidate_rows"][0] == {
        "entry_id": "ADRB2::LIG-1",
        "evidence_tier": "claim_safe",
        "claim_safe": True,
        "backmap_status": "ok",
        "mapping_source": "rdkit_etkdg",
        "site_count": 2,
        "mapped_site_count": 2,
        "donor_count": 1,
        "acceptor_count": 1,
        "max_onsps_sites": 4,
        "polar_site_elements": ["N", "O"],
        "hbond_angle_score": 0.75,
        "two_bead_vs_four_bead_delta": None,
        "reason_code": "",
        "reason_detail": "",
        "report_version": "hbond_backmap_report_v1",
        "claim_boundary": "hbond interpretability only",
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }
    assert summary["gpcr_hard_decoy_metric_ready"] is True
    assert summary["gpcr_broad_claim_allowed"] is False
    assert summary["gpcr_phase3_closure_present"] is True
    assert summary["gpcr_phase3_closure_evidence_ready"] is True
    assert summary["gpcr_phase3_exit_metric_conditions_ready"] is True
    assert summary["gpcr_phase3_broad_promotion_locked"] is True
    assert summary["gpcr_phase3_effective_ranking_pr_auc_ci_low"] == 0.5597832604
    assert summary["gpcr_phase3_effective_top20_hit_rate"] == 1.0
    assert summary["gpcr_phase3_effective_decoys_above_positive_total"] == 0
    assert summary["gpcr_phase3_effective_metric_source"] == "claim_unlock_audit"
    assert summary["gpcr_phase3_promotion_blocker_count"] == 2
    assert summary["gpcr_promotion_work_order_row_count"] == 2
    assert summary["gpcr_promotion_work_order_lane_count"] == 2
    assert summary["gpcr_promotion_work_order_primary_blocker"] == (
        "broad_scope:formal_broad_claim_review_not_approved"
    )
    assert summary["gpcr_promotion_work_order_rows"] == [
        {
            "lane_id": "active_scorer",
            "blocker": "active_scorer:operational_gate_refresh_not_complete",
            "required_action": (
                "Refresh the active scorer operational gate and keep broad GPCR promotion locked."
            ),
            "source_artifact": "runs/gpcr_active_scorer_promotion_decision_packet_current.json",
            "claim_boundary": "GPCR promotion work order only; no broad claim promotion.",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["pocketmd_lite_claim_allowed"] is False
    assert summary["pocketmd_lite_report_evidence_ready"] is False
    assert summary["pocketmd_lite_fill_preview_evidence_ready"] is True
    assert summary["pocketmd_lite_preview_requires_canonical_review"] is True
    assert summary["pocketmd_lite_claim_grade_metric_ready_row_count"] == 2
    assert summary["pocketmd_lite_local_min_ligand_rmsd_a_max"] == 1.29
    assert summary["pocketmd_lite_hbond_persistence_min"] == 0.8
    assert summary["pocketmd_lite_contact_persistence_min"] == 0.9
    assert summary["pocketmd_lite_initial_clash_count_total"] == 79
    assert summary["pocketmd_lite_final_clash_count_total"] == 1
    assert summary["pocketmd_lite_clash_relief_count_total"] == 78
    assert summary["pocketmd_lite_green_band_condition_text"] == (
        "green requires local-min RMSD, hbond/contact persistence, and clash relief."
    )
    assert len(summary["pocketmd_lite_claim_grade_metric_rows"]) == 2
    assert summary["pocketmd_lite_claim_grade_metric_rows"][0] == {
        "entry_id": "ADRB2_GPCR_BLIND:carvedilol",
        "band": "green",
        "uncertainty_posture": "green_low_uncertainty",
        "uncertainty_score": 0.23,
        "claim_grade_metric_ready": True,
        "claim_safe": True,
        "selected_for_refine": True,
        "local_min_ligand_rmsd_a": 1.29,
        "local_min_survived": True,
        "hbond_persistence": 0.8,
        "contact_persistence": 1.0,
        "initial_clash_count": 57,
        "final_clash_count": 0,
        "clash_relief_count": 57,
        "claim_grade_missing_metrics": [],
        "blockers": [],
        "trajectory_probe_status": "pocketmd_lite_metric_collection_probe_ready",
        "candidate_metric_fill_status": "filled_from_claim_grade_probe",
        "recommended_next_local_action": "review_green_band_metrics",
        "candidate_csv_update_allowed": False,
        "refinement_execution_enabled": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }
    assert summary["public_benchmark_claim_allowed"] is False
    assert summary["public_benchmark_receipt_attach_packet_ready"] is False
    assert summary["public_benchmark_receipt_attach_packet_present"] is True
    assert summary["public_benchmark_receipt_attach_lane_row_count"] == 2
    assert summary["public_benchmark_receipt_attach_blocked_lane_count"] == 2
    assert summary["public_benchmark_receipt_attach_primary_blocked_lane_id"] == (
        "vina_gnina_same_input_scores"
    )
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_next_required_step"
    ] == "Fill every Vina/GNINA same-input score template row."
    assert summary["public_benchmark_receipt_attach_primary_blocked_lane_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_source_artifact"
    ] == "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_pending_value_count"
    ] == 32
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_pending_metadata_count"
    ] == 128
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_pending_license_count"
    ] == 16
    assert summary[
        "public_benchmark_receipt_attach_primary_blocked_lane_pending_approval_token_count"
    ] == 16
    assert summary["public_benchmark_receipt_attach_primary_blocked_lane_row"] == {
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
    assert summary["public_benchmark_receipt_attach_lane_rows"][1]["lane_id"] == (
        "metric_source_receipt_rows"
    )
    assert summary["public_benchmark_receipt_attach_lane_rows"][1][
        "pending_value_count"
    ] == 510
    assert summary["public_benchmark_receipt_attach_lane_rows"][1][
        "claim_promotion_allowed"
    ] is False
    assert summary["public_benchmark_vina_gnina_pending_score_count"] == 32
    assert summary["public_benchmark_vina_gnina_pending_field_count"] == 192
    assert summary["public_benchmark_metric_source_pending_field_count"] == 510
    assert summary["public_benchmark_metric_source_pending_approval_token_count"] == 51
    assert summary["public_benchmark_field_work_order_row_count"] == 22
    assert summary["public_benchmark_field_work_order_pending_field_count"] == 702
    assert summary["public_benchmark_field_work_order_primary_field_name"] == "approval_token"
    assert summary["public_benchmark_field_work_order_primary_lane_id"] == (
        "vina_gnina_same_input_scores"
    )
    assert summary["public_benchmark_field_work_order_primary_pending_row_count"] == 16
    assert summary["public_benchmark_field_work_order_primary_required_value"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
    )
    assert summary["public_benchmark_field_work_order_primary_required_action"] == (
        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
        "after operator review."
    )
    assert summary["public_benchmark_field_work_order_primary_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES"
    )
    assert summary["public_benchmark_field_work_order_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["public_benchmark_field_work_order_primary_source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert summary["public_benchmark_field_work_order_rows"] == [
        {
            "lane_id": "vina_gnina_same_input_scores",
            "field_name": "approval_token",
            "pending_row_count": 16,
            "required_value": (
                "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES for approval_token"
            ),
            "required_action": (
                "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
                "after operator review."
            ),
            "approval_token_required": "APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES",
            "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
            "source_artifact": "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
            "claim_boundary": "same-input Vina/GNINA score receipt only",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["public_benchmark_external_receipt_step_rows"] == [
        {
            "step_id": "vina_gnina_same_input_comparison",
            "status": "blocked",
            "ready": False,
            "evidence_artifact": (
                "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
            ),
            "primary_metric": "score_rows=0/16",
            "secondary_metric": "pending_fields=192",
            "blocker": "vina_gnina_same_input_score_evidence_missing",
            "next_required_step": (
                "Fill every score-template row with same-input Vina/GNINA scores."
            ),
            "claim_boundary": "public benchmark audit boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["public_benchmark_primary_blocker_id"] == "vina_gnina_same_input_scores"
    assert summary["public_benchmark_primary_blocker"] == (
        "vina_gnina_same_input_score_evidence_missing"
    )
    assert summary["public_benchmark_primary_next_required_step"] == (
        "Fill the receipt attach packet rows before rerunning the benchmark audit."
    )
    assert summary["public_benchmark_vina_gnina_score_template_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["public_benchmark_vina_gnina_score_template_receipt_json"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert summary["public_benchmark_metric_source_receipt_csv"] == (
        "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
    )
    assert summary["public_benchmark_vina_gnina_adapter_command_after_fill"] == (
        "python3 tools/build_pdbbind_casf_pose_affinity_results.py --comparison-scores-csv "
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["evidence_bundle_export_ready"] is True
    assert summary["evidence_bundle_export_row_count"] == 2
    assert summary["evidence_bundle_export_blocker_row_count"] == 0
    assert summary["evidence_bundle_export_required_missing_row_count"] == 0
    assert summary["evidence_bundle_export_rows"] == [
        {
            "artifact_id": "ai_md_engine_kpi_report_json",
            "role": "local_pc_runtime_report",
            "artifact_path": "runs/ai_md_engine_kpi_report_current.json",
            "bundle_arcname": "runs/ai_md_engine_kpi_report_current.json",
            "required": True,
            "exists": True,
            "missing": False,
            "included_in_bundle": True,
            "release_blocker": False,
            "sha256": "abc123",
            "size_bytes": 143772,
            "claim_boundary": "bundle fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "artifact_id": "optional_runtime_plot",
            "role": "runtime_plot",
            "artifact_path": "runs/ai_md_runtime_scaling_plot_current.svg",
            "bundle_arcname": "runs/ai_md_runtime_scaling_plot_current.svg",
            "required": False,
            "exists": True,
            "missing": False,
            "included_in_bundle": True,
            "release_blocker": False,
            "sha256": "def456",
            "size_bytes": 2048,
            "claim_boundary": "plot artifact row boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["api_customer_flow_release_evidence_present"] is True
    assert summary["api_customer_flow_release_evidence_ready"] is True
    assert summary["api_customer_flow_release_evidence_status"] == "api_customer_flow_release_evidence_ready"
    assert summary["api_customer_flow_release_evidence_pass_count"] == 6
    assert summary["api_customer_flow_release_evidence_blocker_count"] == 0
    assert summary["api_customer_flow_tier_alpha_smoke_status"] == "tier_alpha_adrb2_dispatch_smoke_pass"
    assert summary["api_customer_flow_tier_alpha_runner_execution_ok"] is True
    assert summary["api_customer_flow_result_manifest_signature_verified"] is True
    assert summary["api_customer_flow_restricted_runtime_ready"] is True
    assert summary["api_customer_flow_bundle_validation_ready"] is True
    assert summary["api_customer_flow_release_evidence_row_count"] == 2
    assert summary["api_customer_flow_release_evidence_blocker_row_count"] == 0
    assert summary["api_customer_flow_release_evidence_rows"] == [
        {
            "check_id": "tier_alpha_smoke_live_job_ready",
            "status": "pass",
            "release_blocker": False,
            "artifact_path": "runs/tier_alpha_adrb2_dispatch_smoke_current.json",
            "required": "tier alpha smoke pass",
            "observed": "runner_execution_ok=True",
            "reason": "prove the validated runner drained a restricted job",
            "claim_boundary": "api customer flow fixture boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "check_id": "bundle_validation_ready",
            "status": "pass",
            "release_blocker": False,
            "artifact_path": (
                "runs/product_bundle_contract_current.json;"
                "runs/product_delivery_evidence_contract_current.json"
            ),
            "required": "bundle validation passed",
            "observed": "bundle_validation=True;delivery_claim=True",
            "reason": "customer flow terminates in validated bundle gates",
            "claim_boundary": "bundle validation row boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["customer_shadow_paid_pilot_evidence_ready"] is False
    assert summary["customer_shadow_real_row_count"] == 1
    assert summary["customer_shadow_completed_case_count"] == 0
    assert summary["customer_shadow_required_case_count"] == 3
    assert summary["customer_shadow_missing_case_count"] == 3
    assert summary["customer_shadow_customer_retained_raw_data_count"] == 1
    assert summary["customer_shadow_redistribution_allowed_false_count"] == 1
    assert summary["customer_shadow_anonymized_result_summary_count"] == 1
    assert summary["customer_shadow_reviewer_signoff_count"] == 0
    assert summary["customer_shadow_evidence_blocker_count"] == 2
    assert summary["customer_shadow_work_order_ready"] is False
    assert summary["customer_shadow_work_order_row_count"] == 3
    assert summary["customer_shadow_work_order_primary_case_slot_id"] == "customer_shadow_case_1"
    assert summary["customer_shadow_work_order_primary_required_action"] == (
        "Add one reviewed real customer-shadow metadata row."
    )
    assert summary["customer_shadow_work_order_primary_operator_csv"] == (
        "config/customer_shadow_evidence_intake_template.csv"
    )
    assert summary["customer_shadow_work_order_primary_required_row_kind"] == "customer_shadow"
    assert summary["customer_shadow_work_order_primary_required_raw_data_custody"] == "customer_retained"
    assert summary["customer_shadow_work_order_primary_required_customer_retained_raw_data"] is True
    assert summary["customer_shadow_work_order_primary_required_redistribution_allowed"] is False
    assert summary["customer_shadow_work_order_primary_required_raw_data_stored_in_repo"] is False
    assert summary["customer_shadow_work_order_primary_required_derived_metadata_fields"] == [
        "artifact_fingerprint",
        "case_domain",
        "input_size_class",
        "result_metric_summary",
        "runner_profile",
    ]
    assert summary["customer_shadow_work_order_primary_required_reviewer_signoff_status"] == "approved"
    assert summary["customer_shadow_work_order_primary_required_source_artifact_fingerprint"] == "sha256"
    assert summary["customer_shadow_work_order_rows"] == [
        {
            "work_order_id": "customer_shadow_case_slot_1",
            "case_slot_id": "customer_shadow_case_1",
            "status": "missing_customer_shadow_evidence",
            "required_row_kind": "customer_shadow",
            "operator_csv": "config/customer_shadow_evidence_intake_template.csv",
            "required_action": "Add one reviewed real customer-shadow metadata row.",
            "required_raw_data_custody": "customer_retained",
            "required_customer_retained_raw_data": True,
            "required_redistribution_allowed": False,
            "required_raw_data_stored_in_repo": False,
            "required_derived_metadata_fields": [
                "artifact_fingerprint",
                "case_domain",
                "input_size_class",
                "result_metric_summary",
                "runner_profile",
            ],
            "required_reviewer_signoff_status": "approved",
            "required_source_artifact_fingerprint": "sha256",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["customer_shadow_evidence_row_count"] == 1
    assert summary["customer_shadow_reviewed_evidence_row_count"] == 0
    assert summary["customer_shadow_evidence_rows"] == [
        {
            "case_id": "customer_shadow_case_0",
            "case_slot_id": "customer_shadow_case_0",
            "row_kind": "customer_shadow",
            "case_domain": "gpcr",
            "raw_data_custody": "customer_retained",
            "customer_retained_raw_data": True,
            "raw_data_stored_in_repo": False,
            "redistribution_allowed": False,
            "anonymized_result_summary_present": True,
            "reviewer_id_present": True,
            "reviewer_signoff_status": "pending",
            "reviewed_at_utc": "",
            "source_artifact_fingerprint": "sha256:source",
            "artifact_fingerprint": "sha256:artifact",
            "derived_metadata_fields": [
                "artifact_fingerprint",
                "case_domain",
                "input_size_class",
                "result_metric_summary",
                "runner_profile",
            ],
            "reviewed_customer_shadow_row_ready": False,
            "claim_boundary": "customer shadow fixture boundary",
            "raw_data_ingested": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["customer_shadow_paid_pilot_requirement_row_count"] == 14
    assert summary["customer_shadow_paid_pilot_requirement_blocked_count"] == 10
    assert summary["customer_shadow_paid_pilot_requirement_primary_id"] == (
        "completed_customer_shadow_cases"
    )
    assert summary["customer_shadow_paid_pilot_requirement_primary_blocker"] == (
        "completed_customer_shadow_cases_below_required:0/3"
    )
    assert summary["customer_shadow_paid_pilot_requirement_primary_action"] == (
        "Collect reviewed customer-shadow rows that count toward the minimum."
    )
    assert summary["customer_shadow_paid_pilot_requirement_primary_row"] == {
        "requirement_id": "completed_customer_shadow_cases",
        "requirement_type": "minimum_count",
        "ready": False,
        "observed_count": 0,
        "required_count": 3,
        "required_value": "3",
        "observed_value": "0",
        "blocker": "completed_customer_shadow_cases_below_required:0/3",
        "operator_action": "Collect reviewed customer-shadow rows that count toward the minimum.",
        "paid_pilot_wording_allowed": False,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
    }
    requirement_rows = {
        row["requirement_id"]: row
        for row in summary["customer_shadow_paid_pilot_requirement_rows"]
    }
    assert requirement_rows["customer_shadow_intake_schema_ready"]["ready"] is True
    assert requirement_rows["reviewer_signoff"]["blocker"] == (
        "reviewer_signoff_rows_below_required:0/3"
    )
    assert requirement_rows["customer_shadow_work_order_closed"]["blocker"] == (
        "customer_shadow_work_order_rows_open:3"
    )
    assert requirement_rows["paid_pilot_claim_allowed"]["paid_pilot_wording_allowed"] is False
    assert all(
        row["execution_enabled"] is False
        and row["external_state_mutated"] is False
        and row["claim_promotion_allowed"] is False
        for row in summary["customer_shadow_paid_pilot_requirement_rows"]
    )
    assert summary["customer_shadow_intake_schema_ready"] is True
    assert summary["customer_shadow_minimum_met"] is False
    assert summary["customer_shadow_raw_data_stored_in_repo"] is False
    assert summary["customer_shadow_invalid_row_count"] == 0
    assert summary["customer_shadow_mock_fixture_row_count"] == 0
    assert summary["customer_shadow_required_column_count"] == 12
    assert summary["customer_shadow_redistribution_allowed_required_value"] is False
    assert summary["developer_preview_clean_baseline_ready"] is False
    assert summary["developer_preview_gate_count"] == 6
    assert summary["developer_preview_ready_gate_count"] == 3
    assert summary["developer_preview_blocked_gate_count"] == 3
    assert summary["developer_preview_gate_row_count"] == 2
    assert summary["developer_preview_gate_rows"] == [
        {
            "gate_id": "benchmark_results_clean_checkout_regenerated",
            "priority": "A",
            "status": "blocked_developer_preview_gate",
            "ready": False,
            "receipt_artifacts": (
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
            ),
            "required_receipt_count": 1,
            "present_receipt_count": 1,
            "present_blocked_receipt_count": 1,
            "receipt_blocker_count": 5,
            "primary_metric": "required_ready=false; review_ready=false",
            "secondary_metric": "present_receipts=1; required_receipts=1",
            "blocker": (
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
            ),
            "blockers": [
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
            ],
            "receipt_blockers": [
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                "clean_checkout_benchmark_regenerated_not_true"
            ],
            "next_required_step": "Attach the clean-checkout benchmark receipt.",
            "claim_boundary": "developer preview boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "gate_id": "silent_import_loss_zero",
            "priority": "A",
            "status": "developer_preview_gate_ready",
            "ready": True,
            "receipt_artifacts": (
                ".betelgeuze/developer_preview_silent_import_receipt.json"
            ),
            "required_receipt_count": 1,
            "present_receipt_count": 1,
            "present_blocked_receipt_count": 0,
            "receipt_blocker_count": 0,
            "primary_metric": "silent_import_loss=0",
            "secondary_metric": "present_receipts=1; required_receipts=1",
            "blocker": "",
            "blockers": [],
            "receipt_blockers": [],
            "next_required_step": "",
            "claim_boundary": "developer preview boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["developer_preview_receipt_work_order_row_count"] == 29
    assert summary["developer_preview_receipt_blocker_count"] == 12
    assert summary["developer_preview_receipt_work_order_source_blocker_count"] == 7
    assert summary["developer_preview_primary_blocker_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert summary["developer_preview_receipt_work_order_primary_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert summary["developer_preview_receipt_work_order_primary_receipt_artifact"] == (
        ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    )
    assert summary["developer_preview_receipt_work_order_primary_required_receipt_status"] == (
        "developer_preview_clean_checkout_benchmark_receipt_ready"
    )
    assert summary["developer_preview_receipt_work_order_primary_required_true_fields"] == [
        "clean_checkout_benchmark_regenerated",
        "ai_verify_passed",
        "reviewed_receipt_attached",
    ]
    assert summary["developer_preview_receipt_work_order_primary_required_zero_fields"] == [
        "blocker_count",
        "failed_count",
    ]
    assert summary["developer_preview_receipt_work_order_primary_source_blocker_gate_id"] == (
        "benchmark_results_clean_checkout_regenerated"
    )
    assert summary[
        "developer_preview_receipt_work_order_primary_source_blocker_receipt_artifact"
    ] == ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
    assert summary["developer_preview_receipt_work_order_primary_source_blocker"] == (
        ".betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
    )
    assert summary[
        "developer_preview_receipt_work_order_primary_source_blocker_required_action"
    ] == "Attach the missing source evidence required by the receipt."
    assert summary["developer_preview_receipt_work_order_rows"] == [
        {
            "gate_id": "benchmark_results_clean_checkout_regenerated",
            "priority": "A",
            "receipt_artifact": ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json",
            "receipt_kind": "required",
            "blocker_scope": "receipt_contract",
            "blocker": (
                ".betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:"
                "status=blocked_developer_preview_clean_checkout_benchmark_receipt"
            ),
            "blocker_detail": "status=blocked_developer_preview_clean_checkout_benchmark_receipt",
            "required_action": "Rebuild the receipt after clearing its source blockers.",
            "next_required_step": "Attach the clean-checkout benchmark receipt.",
            "required_receipt_status": "developer_preview_clean_checkout_benchmark_receipt_ready",
            "required_true_field_count": 3,
            "required_true_fields": [
                "clean_checkout_benchmark_regenerated",
                "ai_verify_passed",
                "reviewed_receipt_attached",
            ],
            "required_zero_field_count": 2,
            "required_zero_fields": ["blocker_count", "failed_count"],
            "claim_boundary": "developer preview boundary",
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["f2g_f2h_preflight_present"] is True
    assert summary["f2g_f2h_recovery_packet_present"] is True
    assert summary["f2g_f2h_preflight_status"] == "blocked_f2g_f2h_surface_preflight"
    assert summary["f2g_f2h_recovery_status"] == (
        "f2g_f2h_authoritative_surface_recovery_packet_ready"
    )
    assert summary["f2g_f2h_recovery_required"] is True
    assert summary["f2g_f2h_preflight_blocker_count"] == 8
    assert summary["f2g_f2h_blocked_recovery_item_count"] == 8
    assert summary["f2g_f2h_recovery_item_count"] == 8
    assert summary["f2g_f2h_primary_recovery_item_id"] == "restore_implementation_phase1_tree"
    assert summary["f2g_f2h_primary_required_surface"] == "implementation/phase1"
    assert summary["f2g_f2h_primary_blocker"] == "implementation_phase1_dir_missing"
    assert summary["f2g_f2h_primary_operator_action"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert summary["f2g_f2h_audit_ready"] is False
    assert summary["f2h_continuation_allowed"] is False
    assert summary["f2g_f2h_placeholder_surface_creation_allowed"] is False
    assert summary["f2g_f2h_surface_restore_executed"] is False
    assert summary["f2g_f2h_recovery_rows"] == [
        {
            "recovery_item_id": "restore_implementation_phase1_tree",
            "preflight_check_id": "implementation_phase1_dir",
            "status": "fail",
            "required_surface": "implementation/phase1",
            "observed": "missing",
            "blocker": "implementation_phase1_dir_missing",
            "operator_action": (
                "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
            ),
            "acceptance_rule": "Directory exists in the checkout and is the reviewed implementation tree.",
            "authoritative_source_hint": "Original F2/G1 implementation branch.",
            "prohibited_actions": "do_not_create_placeholder_json;do_not_promote_g1",
            "audit_executed": False,
            "continuation_executed": False,
            "surface_restore_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
        {
            "recovery_item_id": "restore_real_mgt_input_surface",
            "preflight_check_id": "real_mgt_input_surface",
            "status": "fail",
            "required_surface": "real-MGT model/input packet",
            "observed": "",
            "blocker": "real_mgt_input_surface_missing",
            "operator_action": "Restore the reviewed real-MGT model/input packet.",
            "acceptance_rule": "",
            "authoritative_source_hint": "",
            "prohibited_actions": "",
            "audit_executed": False,
            "continuation_executed": False,
            "surface_restore_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        },
    ]
    assert summary["enterprise_on_prem_readiness_present"] is True
    assert summary["enterprise_on_prem_ready"] is False
    assert summary["enterprise_on_prem_claim_allowed"] is False
    assert summary["enterprise_on_prem_control_count"] == 10
    assert summary["enterprise_on_prem_ready_control_count"] == 4
    assert summary["enterprise_on_prem_blocked_control_count"] == 6
    assert summary["enterprise_on_prem_primary_blocker_id"] == "oidc_rbac_tenant_isolation"
    assert summary["enterprise_on_prem_primary_blocker"] == (
        "oidc_rbac_claim_grade_evidence_missing"
    )
    assert summary["enterprise_on_prem_oidc_rbac_ready"] is False
    assert summary["enterprise_on_prem_object_storage_ready"] is False
    assert summary["enterprise_on_prem_gpu_scheduler_ready"] is False
    assert summary["enterprise_on_prem_audit_provenance_metrics_tracing_ready"] is False
    assert summary["enterprise_on_prem_license_control_ready"] is True
    assert summary["enterprise_on_prem_support_bundle_recovery_drill_ready"] is False
    assert summary["enterprise_on_prem_rollback_retry_idempotency_ready"] is True
    assert summary["enterprise_on_prem_control_rows"] == [
        {
            "control_id": "oidc_rbac_tenant_isolation",
            "title": "OIDC/RBAC and tenant isolation",
            "status": "blocked_oidc_rbac_not_verified",
            "ready": False,
            "blocker": "oidc_rbac_claim_grade_evidence_missing",
            "next_action": (
                "Add reviewed OIDC provider, RBAC role matrix, and tenant-isolation test receipts."
            ),
            "evidence": "auth_ready=true;tenant_isolation_ready=true;oidc_ready=false;rbac_ready=false",
            "evidence_artifacts": ["runs/product_security_deployment_contract_current.json"],
            "claim_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["pr38_split_acceptance_present"] is True
    assert summary["pr38_split_acceptance_status"] == "pr38_split_acceptance_packet_ready"
    assert summary["pr38_split_acceptance_ready"] is True
    assert summary["pr38_child_pr_verification_matrix_present"] is True
    assert summary["pr38_child_pr_verification_matrix_status"] == (
        "pr38_child_pr_verification_matrix_ready"
    )
    assert summary["pr38_child_pr_verification_matrix_ready"] is True
    assert summary["pr38_split_ready_for_human_branch_approval"] is True
    assert summary["pr38_operator_branch_approval_required"] is True
    assert summary["pr38_child_pr_count"] == 5
    assert summary["pr38_ready_child_pr_count"] == 5
    assert summary["pr38_blocked_child_pr_count"] == 0
    assert summary["pr38_focused_test_required_count"] == 5
    assert summary["pr38_ai_verify_required_count"] == 5
    assert summary["pr38_product_mode_required_count"] == 5
    assert summary["pr38_hunk_split_review_required_count"] == 2
    assert summary["pr38_claim_boundary_review_required_count"] == 5
    assert summary["pr38_product_mode_expected_result"] == (
        "pass_product_smoke_claim_boundaries_locked"
    )
    assert summary["pr38_product_mode_expected_fail_closed_blockers"] == []
    assert summary["pr38_product_mode_claim_boundary_expected_locks"] == [
        "paid_pilot_wording_allowed=false",
        "public_benchmark_claim_allowed=false",
        "gpcr_broad_claim_allowed=false",
        "pocketmd_lite_claim_allowed=false",
        "f2g_f2h_placeholder_surface_creation_allowed=false",
        "f2h_continuation_allowed=false",
    ]
    assert summary["pr38_paid_pilot_wording_allowed"] is False
    assert summary["pr38_branch_commit_work_allowed"] is False
    assert summary["pr38_patches_applied"] is False
    assert summary["pr38_branches_created"] is False
    assert summary["pr38_next_slice_id"] == "f2g_f2h_preflight"
    assert summary["pr38_next_ai_verify_command"] == "./scripts/ai-verify.sh"
    assert summary["pm_priority_queue_present"] is True
    assert summary["pm_priority_queue_status"] == "blocked_pm_priority_queue"
    assert summary["pm_priority_queue_blocked_item_count"] == 5
    assert summary["pm_priority_queue_first_blocked_item_id"] == "2"
    assert summary["pm_priority_queue_first_blocker"] == "f2g_authoritative_surfaces_missing"
    assert summary["pm_priority_queue_next_required_step"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert summary["next_required_step"] == (
        "Clear third-party license review gate before release."
    )

    assert panels["product_capabilities_dashboard"]["route"] == "/product/capabilities"
    assert panels["goal_readiness_dashboard"]["route"] == "/goal/readiness"
    assert panels["hbond_backmap_candidate_table"]["route"] == "/product/hbond-backmap-report"
    assert panels["hbond_backmap_candidate_table"]["source_artifact_ready"] is True
    assert "candidate_count=2" in panels["hbond_backmap_candidate_table"]["primary_metric"]
    assert panels["hbond_backmap_candidate_table"]["blockers"] == []
    assert "pr_auc_ci_low=0.5598" in panels["gpcr_hard_decoy_blocker_panel"]["primary_metric"]
    assert panels["gpcr_hard_decoy_blocker_panel"]["claim_allowed"] is False
    assert "top20_hit_rate=1" in panels["gpcr_hard_decoy_blocker_panel"]["primary_metric"]
    assert "decoys_above_positive=0" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "phase3_closure_ready=true" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "phase3_exit_metric_ready=true" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "phase3_metric_source=claim_unlock_audit" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "broad_promotion_locked=true" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "promotion_blockers=2" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert panels["gpcr_hard_decoy_blocker_panel"]["next_action"] == "Keep broad GPCR promotion locked."
    assert "promotion_work_order_rows=2" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "promotion_work_order_lanes=2" in panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    assert "promotion_work_order_primary=broad_scope:formal_broad_claim_review_not_approved" in (
        panels["gpcr_hard_decoy_blocker_panel"]["secondary_metric"]
    )
    assert panels["pocketmd_lite_report_panel"]["operator_action_required"] is True
    assert "green=5" in panels["pocketmd_lite_report_panel"]["primary_metric"]
    assert "abstain=0" in panels["pocketmd_lite_report_panel"]["primary_metric"]
    assert "report_ready=false" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "preview_ready=true" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "local_min_rmsd_max=1.29" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "hbond_persistence_min=0.8" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "contact_persistence_min=0.9" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "initial_clashes=79" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "final_clashes=1" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "clash_relief=78" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert "promotion_allowed=false" in panels["pocketmd_lite_report_panel"]["secondary_metric"]
    assert panels["pocketmd_lite_report_panel"]["blockers"] == [
        "pocketmd_lite_preview_not_canonical_report"
    ]
    assert panels["public_benchmark_scorecard"]["route"] == "/product/public-benchmark-external-receipts-audit"
    assert "ready_steps=5" in panels["public_benchmark_scorecard"]["primary_metric"]
    assert "blocked_steps=2" in panels["public_benchmark_scorecard"]["primary_metric"]
    assert "blocked_receipt_rows=51" in panels["public_benchmark_scorecard"]["primary_metric"]
    assert "vina_gnina_score_evidence=false" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "attach_packet_ready=false" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "receipt_attach_lanes=2" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "receipt_attach_blocked_lanes=2" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "receipt_primary_lane=vina_gnina_same_input_scores" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "receipt_primary_pending_values=32" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "receipt_primary_pending_metadata=128" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "receipt_primary_pending_license=16" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "receipt_primary_pending_tokens=16" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "receipt_primary_operator_csv=runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "receipt_primary_source=runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "pending_scores=32" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "pending_score_fields=192" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "pending_receipt_fields=510" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "pending_receipt_tokens=51" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "field_work_order_rows=22" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "field_work_order_pending_fields=702" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "field_work_order_primary=approval_token" in panels["public_benchmark_scorecard"]["secondary_metric"]
    assert "field_work_order_lane=vina_gnina_same_input_scores" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "field_work_order_primary_rows=16" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "field_work_order_required_value=APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
        "for approval_token"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "primary_blocker_id=vina_gnina_same_input_scores" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert "primary_blocker=vina_gnina_same_input_score_evidence_missing" in (
        panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "score_template=runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "score_receipt=runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "metric_receipt=config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert (
        "adapter_after_fill=python3 tools/build_pdbbind_casf_pose_affinity_results.py --comparison-scores-csv "
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
        in panels["public_benchmark_scorecard"]["secondary_metric"]
    )
    assert panels["public_benchmark_scorecard"]["blockers"] == [
        "vina_gnina_same_input_scores:vina_gnina_same_input_score_evidence_missing",
        "metric_source_receipt_rows:benchmark_metric_source_receipt_rows_unapproved",
    ]
    assert panels["public_benchmark_scorecard"]["next_action"] == (
        "Fill every Vina/GNINA same-input score template row."
    )
    assert panels["release_blockers_operator_actions"]["claim_allowed"] is False
    assert panels["release_blockers_operator_actions"]["status"] == "pm_priority_queue_blocked"
    assert panels["release_blockers_operator_actions"]["operator_action_required"] is True
    assert "release_allowed=false" in panels["release_blockers_operator_actions"]["primary_metric"]
    assert "restricted_release_allowed=false" in (
        panels["release_blockers_operator_actions"]["primary_metric"]
    )
    assert "decision_release_allowed=false" in (
        panels["release_blockers_operator_actions"]["primary_metric"]
    )
    assert "decision_blockers=1" in panels["release_blockers_operator_actions"]["primary_metric"]
    assert "pm_queue_blocked_items=5" in panels["release_blockers_operator_actions"]["primary_metric"]
    assert "decision_gate=blocked_goal_release_decision" in (
        panels["release_blockers_operator_actions"]["secondary_metric"]
    )
    assert "decision_primary_check=third_party_license_review_gate_recorded" in (
        panels["release_blockers_operator_actions"]["secondary_metric"]
    )
    assert (
        "decision_primary_artifact=runs/third_party_license_review_gate_current.json"
        in panels["release_blockers_operator_actions"]["secondary_metric"]
    )
    assert "pm_first_blocked_item=2" in panels["release_blockers_operator_actions"]["secondary_metric"]
    assert "pm_first_blocker=f2g_authoritative_surfaces_missing" in (
        panels["release_blockers_operator_actions"]["secondary_metric"]
    )
    assert panels["release_blockers_operator_actions"]["next_action"] == (
        "Clear third-party license review gate before release."
    )
    assert panels["release_blockers_operator_actions"]["blockers"] == [
        (
            "The final release decision must keep JSZip dual-license "
            "redistribution review visible as an operator/legal boundary."
        ),
        "f2g_authoritative_surfaces_missing",
    ]
    assert summary["release_allowed"] is False
    assert summary["release_decision_present"] is True
    assert summary["release_decision_status"] == "blocked_goal_release_decision"
    assert summary["release_decision_release_allowed"] is False
    assert summary["release_decision_restricted_release_allowed"] is False
    assert summary["release_decision_blocker_count"] == 1
    assert (
        summary["release_decision_primary_blocker_check"]
        == "third_party_license_review_gate_recorded"
    )
    assert summary["release_decision_primary_blocker_reason"] == (
        "The final release decision must keep JSZip dual-license "
        "redistribution review visible as an operator/legal boundary."
    )
    assert (
        summary["release_decision_primary_blocker_required"]
        == "third-party license review gate ready for JSZip"
    )
    assert (
        summary["release_decision_primary_blocker_artifact"]
        == "runs/third_party_license_review_gate_current.json"
    )
    assert summary["release_decision_rows"] == [
        {
            "lane_id": "commercial_product_release",
            "check": "third_party_license_review_gate_recorded",
            "status": "fail",
            "release_blocker": True,
            "artifact_path": "runs/third_party_license_review_gate_current.json",
            "required": "third-party license review gate ready for JSZip",
            "observed": "third_party_license_review_gate_ready;review_csv_present=false",
            "reason": (
                "The final release decision must keep JSZip dual-license "
                "redistribution review visible as an operator/legal boundary."
            ),
            "action_executed": False,
            "delete_executed": False,
            "outbound_email_enabled": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
        }
    ]
    assert summary["release_operator_action_row_count"] == 1
    assert summary["release_operator_action_primary_lane_id"] == "product_ai_production"
    assert (
        summary["release_operator_action_primary_action_type"]
        == "complete_residual_registry_guarded_promotion"
    )
    assert summary["release_operator_action_primary_status"] == "required"
    assert (
        summary["release_operator_action_primary_approval_token"]
        == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    )
    assert (
        summary["release_operator_action_primary_required_input"]
        == "production_promotion_allowed;default_residual_mode"
    )
    assert "tools/build_residual_model_registry.py" in (
        summary["release_operator_action_primary_command"]
    )
    assert summary["release_operator_action_rows"] == [
        {
            "lane_id": "product_ai_production",
            "action_type": "complete_residual_registry_guarded_promotion",
            "status": "required",
            "priority": 0,
            "approval_token": "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION",
            "required_input": "production_promotion_allowed;default_residual_mode",
            "artifact_path": (
                "runs/product_goal_completion_audit_current.json;"
                "runs/residual_model_registry_current.json"
            ),
            "command": (
                "python3 tools/build_residual_model_registry.py && "
                "python3 tools/build_product_production_ai_checkpoint_readiness.py"
            ),
            "reason": "registry promotion gates are not satisfied",
            "recommended_action": (
                "Complete the guarded production AI registry promotion receipt."
            ),
            "operator_completion_artifact_id": (
                "residual_model_registry_guarded_promotion"
            ),
            "operator_completion_completion_rule": (
                "registry_promotion_missing_gate_count=0"
            ),
            "operator_completion_next_action": (
                "Complete the guarded production AI registry promotion receipt."
            ),
            "operator_completion_required_fields_or_columns": (
                "production_promotion_allowed;default_residual_mode"
            ),
            "parallelizable_with_primary_action": True,
            "parallel_lane_precondition": "claim promotion remains locked",
            "action_executed": False,
            "delete_executed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_promotion_allowed": False,
            "claim_boundary": "unsafe fixture value should be preserved as text only",
        }
    ]
    assert panels["evidence_bundle_export"]["source_artifact_ready"] is True
    assert "api_customer_flow_ready=true" in panels["evidence_bundle_export"]["secondary_metric"]
    assert "tier_alpha=tier_alpha_adrb2_dispatch_smoke_pass" in (
        panels["evidence_bundle_export"]["secondary_metric"]
    )
    assert "signed_manifest=true" in panels["evidence_bundle_export"]["secondary_metric"]
    assert "restricted_runtime=true" in panels["evidence_bundle_export"]["secondary_metric"]
    assert "api_bundle_validation=true" in panels["evidence_bundle_export"]["secondary_metric"]
    assert "customer_rows=0" in panels["claim_boundary_matrix"]["primary_metric"]
    assert "required_customer_rows=3" in panels["claim_boundary_matrix"]["primary_metric"]
    assert "real_rows=1" in panels["claim_boundary_matrix"]["secondary_metric"]
    assert "missing_customer_rows=3" in panels["claim_boundary_matrix"]["secondary_metric"]
    assert "customer_shadow_blockers=2" in panels["claim_boundary_matrix"]["secondary_metric"]
    assert "customer_shadow_work_order_ready=false" in panels["claim_boundary_matrix"]["secondary_metric"]
    assert "customer_shadow_work_order_rows=3" in panels["claim_boundary_matrix"]["secondary_metric"]
    assert "customer_shadow_work_order_primary=customer_shadow_case_1" in (
        panels["claim_boundary_matrix"]["secondary_metric"]
    )
    assert (
        "customer_shadow_work_order_action=Add one reviewed real customer-shadow metadata row."
        in panels["claim_boundary_matrix"]["secondary_metric"]
    )
    assert panels["customer_shadow_evidence_panel"]["route"] == "/goal/customer-shadow"
    assert panels["customer_shadow_evidence_panel"]["source_artifact_ready"] is True
    assert panels["customer_shadow_evidence_panel"]["operator_action_required"] is True
    assert panels["customer_shadow_evidence_panel"]["claim_allowed"] is False
    assert "completed_cases=0" in panels["customer_shadow_evidence_panel"]["primary_metric"]
    assert "required_cases=3" in panels["customer_shadow_evidence_panel"]["primary_metric"]
    assert "missing_cases=3" in panels["customer_shadow_evidence_panel"]["primary_metric"]
    assert "minimum_met=false" in panels["customer_shadow_evidence_panel"]["primary_metric"]
    assert "schema_ready=true" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "real_rows=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "evidence_rows=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "reviewed_evidence_rows=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "mock_rows=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "invalid_rows=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "retained_raw_data=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "raw_data_in_repo=false" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "redistribution_false=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "redistribution_required=false" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "anonymized_summaries=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "reviewer_signoffs=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "required_columns=12" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "paid_pilot_requirements=14" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "paid_pilot_blocked_requirements=10" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "paid_pilot_primary_requirement=completed_customer_shadow_cases" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "paid_pilot_primary_blocker=completed_customer_shadow_cases_below_required:0/3" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "work_order_rows=3" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "work_order_primary=customer_shadow_case_1" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "required_raw_custody=customer_retained" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "required_retained_raw_data=true" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "required_raw_data_in_repo=false" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "required_derived_metadata_fields=5" in (
        panels["customer_shadow_evidence_panel"]["secondary_metric"]
    )
    assert "required_signoff=approved" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert panels["customer_shadow_evidence_panel"]["blockers"] == [
        "completed_customer_shadow_cases_below_required:0/3"
    ]
    assert panels["customer_shadow_evidence_panel"]["next_action"] == (
        "Collect reviewed customer-shadow rows that count toward the minimum."
    )
    assert panels["customer_shadow_evidence_panel"]["disallowed_claim_text"] == (
        "Paid-pilot wording remains disallowed until three reviewed customer-shadow rows pass."
    )
    assert panels["developer_preview_final_gates"]["route"] == "/goal/developer-preview"
    assert panels["developer_preview_final_gates"]["source_artifact_ready"] is True
    assert panels["developer_preview_final_gates"]["operator_action_required"] is True
    assert panels["developer_preview_final_gates"]["claim_allowed"] is False
    assert panels["developer_preview_final_gates"]["claim_boundary"] == "developer preview boundary"
    assert "ready_gates=3/6" in panels["developer_preview_final_gates"]["primary_metric"]
    assert "blocked_gates=3" in panels["developer_preview_final_gates"]["primary_metric"]
    assert "clean_baseline=false" in panels["developer_preview_final_gates"]["primary_metric"]
    assert "receipt_work_order_rows=29" in panels["developer_preview_final_gates"]["secondary_metric"]
    assert "receipt_blockers=12" in panels["developer_preview_final_gates"]["secondary_metric"]
    assert "source_blockers=7" in panels["developer_preview_final_gates"]["secondary_metric"]
    assert "primary_gate=benchmark_results_clean_checkout_regenerated" in (
        panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert "primary_blocker=benchmark_results_clean_checkout_regenerated" in (
        panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert (
        "primary_receipt=.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
        in panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert (
        "primary_expected_status=developer_preview_clean_checkout_benchmark_receipt_ready"
        in panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert "primary_required_true_fields=3" in (
        panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert "primary_required_zero_fields=2" in (
        panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert "primary_source_gate=benchmark_results_clean_checkout_regenerated" in (
        panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert (
        "primary_source_receipt=.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json"
        in panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert (
        "primary_source_blocker=.betelgeuze/developer_preview_clean_checkout_ai_verify.log:missing"
        in panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert (
        "primary_source_action=Attach the missing source evidence required by the receipt."
        in panels["developer_preview_final_gates"]["secondary_metric"]
    )
    assert panels["developer_preview_final_gates"]["next_action"] == (
        "Attach the clean-checkout benchmark receipt."
    )
    assert panels["developer_preview_final_gates"]["blockers"] == [
        "benchmark_results_clean_checkout_regenerated:.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:status=blocked_developer_preview_clean_checkout_benchmark_receipt"
    ]
    assert panels["f2g_f2h_preflight_work_order"]["route"] == "/goal/priority-queue#f2g-f2h"
    assert panels["f2g_f2h_preflight_work_order"]["source_artifact_ready"] is True
    assert panels["f2g_f2h_preflight_work_order"]["operator_action_required"] is True
    assert panels["f2g_f2h_preflight_work_order"]["claim_allowed"] is False
    assert panels["f2g_f2h_preflight_work_order"]["claim_boundary"] == "f2g recovery boundary"
    assert "preflight_blockers=8" in panels["f2g_f2h_preflight_work_order"]["primary_metric"]
    assert "blocked_recovery_items=8" in panels["f2g_f2h_preflight_work_order"]["primary_metric"]
    assert "recovery_items=8" in panels["f2g_f2h_preflight_work_order"]["primary_metric"]
    assert "f2g_audit_ready=false" in panels["f2g_f2h_preflight_work_order"]["primary_metric"]
    assert "f2h_allowed=false" in panels["f2g_f2h_preflight_work_order"]["primary_metric"]
    assert "recovery_required=true" in panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    assert "primary_recovery_item=restore_implementation_phase1_tree" in (
        panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    )
    assert "primary_required_surface=implementation/phase1" in (
        panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    )
    assert "primary_blocker=implementation_phase1_dir_missing" in (
        panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    )
    assert "placeholder_allowed=false" in panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    assert "surface_restore_executed=false" in (
        panels["f2g_f2h_preflight_work_order"]["secondary_metric"]
    )
    assert panels["f2g_f2h_preflight_work_order"]["next_action"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert panels["enterprise_on_prem_readiness_panel"]["route"] == "/goal/enterprise-on-prem"
    assert panels["enterprise_on_prem_readiness_panel"]["source_artifact_ready"] is True
    assert panels["enterprise_on_prem_readiness_panel"]["operator_action_required"] is True
    assert panels["enterprise_on_prem_readiness_panel"]["claim_allowed"] is False
    assert panels["enterprise_on_prem_readiness_panel"]["claim_boundary"] == "enterprise boundary"
    assert "ready_controls=4/10" in panels["enterprise_on_prem_readiness_panel"]["primary_metric"]
    assert "blocked_controls=6" in panels["enterprise_on_prem_readiness_panel"]["primary_metric"]
    assert "primary_blocker_id=oidc_rbac_tenant_isolation" in (
        panels["enterprise_on_prem_readiness_panel"]["secondary_metric"]
    )
    assert "object_storage_ready=false" in panels["enterprise_on_prem_readiness_panel"]["secondary_metric"]
    assert "gpu_scheduler_ready=false" in panels["enterprise_on_prem_readiness_panel"]["secondary_metric"]
    assert panels["enterprise_on_prem_readiness_panel"]["blockers"] == [
        "oidc_rbac_claim_grade_evidence_missing"
    ]
    assert panels["pr38_child_pr_split_queue"]["route"] == (
        "/product/operator-cockpit#pr38-child-pr-split"
    )
    assert panels["pr38_child_pr_split_queue"]["source_artifact_ready"] is True
    assert panels["pr38_child_pr_split_queue"]["operator_action_required"] is True
    assert panels["pr38_child_pr_split_queue"]["claim_allowed"] is False
    assert panels["pr38_child_pr_split_queue"]["claim_boundary"] == (
        "pr38 child verification boundary"
    )
    assert "child_prs=5" in panels["pr38_child_pr_split_queue"]["primary_metric"]
    assert "ready=5" in panels["pr38_child_pr_split_queue"]["primary_metric"]
    assert "blocked=0" in panels["pr38_child_pr_split_queue"]["primary_metric"]
    assert "focused_tests=5" in panels["pr38_child_pr_split_queue"]["primary_metric"]
    assert "ai_verify=5" in panels["pr38_child_pr_split_queue"]["primary_metric"]
    assert "product_mode=5" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "hunk_review=2" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "claim_review=5" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "branch_commit_allowed=false" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "patches_applied=false" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "branches_created=false" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert "next_slice=f2g_f2h_preflight" in panels["pr38_child_pr_split_queue"]["secondary_metric"]
    assert panels["pr38_child_pr_split_queue"]["blockers"] == [
        "human_branch_commit_approval_required"
    ]
    assert "paid-pilot" in panels["pr38_child_pr_split_queue"]["disallowed_claim_text"]
    assert panels["f2g_f2h_preflight_work_order"]["blockers"] == [
        "implementation_phase1_dir_missing",
        "real_mgt_input_surface_missing",
        "f2h_blocked_until_f2g_audit",
    ]

    assert claims["operator_cockpit_surface"]["allowed"] is True
    assert claims["pocketmd_lite_refinement_evidence"]["allowed"] is True
    assert claims["paid_pilot_wording"]["allowed"] is False
    assert claims["general_platform_claim"]["allowed"] is False
    assert claims["broad_gpcr_claim"]["allowed"] is False
    assert claims["pocketmd_lite_customer_claim"]["allowed"] is False
    assert claims["public_benchmark_claim"]["allowed"] is False
    assert claims["enterprise_on_prem_platform_claim"]["allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_product_operator_cockpit_writes_outputs(tmp_path: Path) -> None:
    payload = _build_payload(tmp_path)

    mod.write_product_operator_cockpit_outputs(
        payload,
        out_json=tmp_path / "runs/product_operator_cockpit_current.json",
        out_csv=tmp_path / "runs/product_operator_cockpit_current.csv",
        out_md=tmp_path / "runs/product_operator_cockpit_current.md",
        out_html=tmp_path / "runs/product_operator_cockpit_current.html",
        root=tmp_path,
    )

    written = json.loads((tmp_path / "runs/product_operator_cockpit_current.json").read_text(encoding="utf-8"))
    html = (tmp_path / "runs/product_operator_cockpit_current.html").read_text(encoding="utf-8")
    csv_text = (tmp_path / "runs/product_operator_cockpit_current.csv").read_text(encoding="utf-8")
    md = (tmp_path / "runs/product_operator_cockpit_current.md").read_text(encoding="utf-8")

    assert written["summary"]["required_phase8_panel_count"] == 9
    assert "Product Operator Cockpit" in html
    assert "H-Bond BackMap candidate table" in html
    assert "PR #38 child PR split queue" in html
    assert "Allowed/disallowed claim text" in html
    assert "paid_pilot_wording" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "public_benchmark_scorecard" in csv_text
    assert "pr38_child_pr_split_queue" in csv_text
    assert "paid_pilot_wording_allowed: false" in md
    assert "pr38_child_pr_split_queue" in md


def test_product_operator_cockpit_cli_writes_current_artifacts(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    out_json = tmp_path / "runs/product_operator_cockpit_current.json"
    out_html = tmp_path / "runs/product_operator_cockpit_current.html"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/product/build_product_operator_cockpit.py"),
            "--capabilities-json",
            str(paths["capabilities"]),
            "--goal-readiness-json",
            str(paths["goal"]),
            "--hbond-json",
            str(paths["hbond"]),
            "--gpcr-json",
            str(paths["gpcr"]),
            "--pocketmd-json",
            str(paths["pocketmd"]),
            "--public-benchmark-json",
            str(paths["public"]),
            "--public-benchmark-receipt-attach-packet-json",
            str(paths["public_attach"]),
            "--release-actions-json",
            str(paths["release"]),
            "--pm-priority-queue-json",
            str(paths["pm_queue"]),
            "--evidence-bundle-json",
            str(paths["bundle"]),
            "--customer-shadow-json",
            str(paths["customer"]),
            "--developer-preview-json",
            str(paths["developer_preview"]),
            "--f2g-f2h-preflight-json",
            str(paths["f2g_preflight"]),
            "--f2g-f2h-recovery-json",
            str(paths["f2g_recovery"]),
            "--pr38-split-acceptance-json",
            str(paths["pr38_acceptance"]),
            "--pr38-child-pr-verification-matrix-json",
            str(paths["pr38_matrix"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "runs/product_operator_cockpit_current.csv"),
            "--out-md",
            str(tmp_path / "runs/product_operator_cockpit_current.md"),
            "--out-html",
            str(out_html),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["phase8_surface_ready"] is True
    assert out_html.exists()
