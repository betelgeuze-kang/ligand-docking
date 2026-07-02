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
                "primary_blocker_next_required_step": (
                    "Attach operator-provided Vina/GNINA scores for the same subset rows, then rerun the adapter."
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
                "blockers": [
                    "vina_gnina_same_input_scores:vina_gnina_same_input_score_evidence_missing",
                    "metric_source_receipt_rows:benchmark_metric_source_receipt_rows_unapproved",
                ],
                "vina_gnina_score_value_pending_count": 32,
                "metric_source_receipt_manual_field_pending_count": 510,
                "metric_source_receipt_approval_token_pending_count": 51,
                "field_work_order_row_count": 22,
                "field_work_order_pending_field_count": 702,
                "field_work_order_primary_field_name": "approval_token",
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
                "real_customer_shadow_row_count": 1,
                "completed_customer_shadow_case_count": 0,
                "required_completed_customer_shadow_case_count": 3,
                "missing_completed_customer_shadow_case_count": 3,
                "customer_retained_raw_data_count": 1,
                "redistribution_allowed_false_count": 1,
                "anonymized_result_summary_count": 1,
                "reviewer_signoff_count": 0,
                "blocker_count": 2,
                "customer_shadow_work_order_ready": False,
                "customer_shadow_work_order_row_count": 3,
                "customer_shadow_work_order_primary_case_slot_id": "customer_shadow_case_1",
                "customer_shadow_work_order_primary_required_action": (
                    "Add one reviewed real customer-shadow metadata row."
                ),
                "paid_pilot_evidence_ready": False,
                "paid_pilot_claim_allowed": False,
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
    assert summary["observed_phase8_panel_count"] == 9
    assert summary["missing_required_phase8_panel_count"] == 0
    assert summary["paid_pilot_wording_allowed"] is False
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
    assert panels["public_benchmark_scorecard"]["blockers"] == [
        "vina_gnina_same_input_scores:vina_gnina_same_input_score_evidence_missing",
        "metric_source_receipt_rows:benchmark_metric_source_receipt_rows_unapproved",
    ]
    assert panels["public_benchmark_scorecard"]["next_action"] == (
        "Fill the receipt attach packet rows before rerunning the benchmark audit."
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

    assert claims["operator_cockpit_surface"]["allowed"] is True
    assert claims["paid_pilot_wording"]["allowed"] is False
    assert claims["general_platform_claim"]["allowed"] is False
    assert claims["broad_gpcr_claim"]["allowed"] is False
    assert claims["pocketmd_lite_customer_claim"]["allowed"] is False
    assert claims["public_benchmark_claim"]["allowed"] is False
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
