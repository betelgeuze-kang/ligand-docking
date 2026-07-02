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
            }
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
            }
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
                {"entry_id": "ADRB2::LIG-1", "claim_safe": True},
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
            }
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
                    "claim_grade_metric_ready": True,
                    "local_min_ligand_rmsd_a": 1.29,
                    "hbond_persistence": 0.8,
                    "contact_persistence": 1.0,
                    "initial_clash_count": 57,
                    "clash_count": 0,
                    "clash_relief_count": 57,
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
            }
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
            }
        },
    )
    _write_json(
        paths["release"],
        {
            "summary": {
                "status": "operator_actions_required",
                "goal_release_allowed": False,
                "goal_release_blocker_count": 4,
                "primary_action_id": "product_ai_production:complete_residual_registry_guarded_promotion",
                "primary_action_recommended_action": "Complete the guarded production AI registry promotion receipt.",
                "goal_release_decision_gate_status": "blocked_goal_release_decision",
            }
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
            }
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
            }
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
            }
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
                "primary_blocker_id": "benchmark_results_clean_checkout_regenerated",
                "next_required_step": "Attach the clean-checkout benchmark receipt.",
                "blockers": [
                    "benchmark_results_clean_checkout_regenerated:.betelgeuze/developer_preview_clean_checkout_benchmark_receipt.json:status=blocked_developer_preview_clean_checkout_benchmark_receipt"
                ],
                "claim_boundary": "developer preview boundary",
            }
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
                    "blocker": "implementation_phase1_dir_missing",
                    "operator_action": (
                        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
                    ),
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
            }
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
        release_actions_json=paths["release"],
        pm_priority_queue_json=paths["pm_queue"],
        evidence_bundle_json=paths["bundle"],
        api_customer_flow_json=paths["api_customer_flow"],
        customer_shadow_json=paths["customer"],
        developer_preview_json=paths["developer_preview"],
        f2g_f2h_preflight_json=paths["f2g_preflight"],
        f2g_f2h_recovery_json=paths["f2g_recovery"],
        enterprise_on_prem_json=paths["enterprise"],
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
    assert summary["observed_phase8_panel_count"] == 13
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
    assert summary["general_platform_claim_allowed"] is False
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
    assert summary["public_benchmark_claim_allowed"] is False
    assert summary["public_benchmark_receipt_attach_packet_ready"] is False
    assert summary["public_benchmark_receipt_attach_packet_present"] is True
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
    assert summary["developer_preview_receipt_work_order_row_count"] == 29
    assert summary["developer_preview_receipt_blocker_count"] == 12
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
    assert summary["pm_priority_queue_present"] is True
    assert summary["pm_priority_queue_status"] == "blocked_pm_priority_queue"
    assert summary["pm_priority_queue_blocked_item_count"] == 5
    assert summary["pm_priority_queue_first_blocked_item_id"] == "2"
    assert summary["pm_priority_queue_first_blocker"] == "f2g_authoritative_surfaces_missing"
    assert summary["pm_priority_queue_next_required_step"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert summary["next_required_step"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
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
        "Fill approval_token with APPROVE_PUBLIC_BENCHMARK_VINA_GNINA_SAME_INPUT_SCORES "
        "after operator review."
    )
    assert panels["release_blockers_operator_actions"]["claim_allowed"] is False
    assert panels["release_blockers_operator_actions"]["status"] == "pm_priority_queue_blocked"
    assert panels["release_blockers_operator_actions"]["operator_action_required"] is True
    assert "pm_queue_blocked_items=5" in panels["release_blockers_operator_actions"]["primary_metric"]
    assert "pm_first_blocked_item=2" in panels["release_blockers_operator_actions"]["secondary_metric"]
    assert "pm_first_blocker=f2g_authoritative_surfaces_missing" in (
        panels["release_blockers_operator_actions"]["secondary_metric"]
    )
    assert panels["release_blockers_operator_actions"]["next_action"] == (
        "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight."
    )
    assert panels["release_blockers_operator_actions"]["blockers"] == [
        "f2g_authoritative_surfaces_missing"
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
    assert "mock_rows=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "invalid_rows=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "retained_raw_data=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "raw_data_in_repo=false" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "redistribution_false=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "redistribution_required=false" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "anonymized_summaries=1" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "reviewer_signoffs=0" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
    assert "required_columns=12" in panels["customer_shadow_evidence_panel"]["secondary_metric"]
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
        "Add one reviewed real customer-shadow metadata row."
    ]
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
    assert "Allowed/disallowed claim text" in html
    assert "paid_pilot_wording" in html
    assert "http://" not in html
    assert "https://" not in html
    assert "public_benchmark_scorecard" in csv_text
    assert "paid_pilot_wording_allowed: false" in md


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
