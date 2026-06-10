from __future__ import annotations

from tools import build_post_p0_claim_blocker_rollup as mod


def test_build_post_p0_claim_blocker_rollup_orders_claim_blockers() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ci_low_blocker": True,
                "ranking_pr_auc_ci_low": 0.128,
                "threshold": 0.45,
                "ranking_positive_count": 6,
                "ranking_topk_hit_rate": 0.25,
            },
            "rank_diagnostics": {
                "top20_hit_rate_max_possible": 0.3,
                "top20_missing_positives": [{"ligand_id": "pindolol"}],
            },
            "claim_coverage_requirement": {
                "positive_coverage_gap": 3,
                "required_next_evidence": ["add at least 3 non-leaky GPCR positive examples"],
                "ci_low_policy": {"status": "blocked"},
            },
        },
        {
            "summary": {
                "claim_scope": "post_p0_quality_followup_only",
                "claim_promotion_allowed": False,
                "claim_policy_status": "blocked_post_p0_quality_followup",
                "primary_blocker": "binding_energy_proxy_too_weak_for_translation",
                "translation_gate_focus_score": 68.1,
                "failed_evidence_count": 1,
                "measurement_gap_count": 4,
                "next_required_step": "Close translation-quality evidence before broad claims.",
            }
        },
        {
            "summary": {
                "authoritative_apply_ready": False,
                "blocker_count": 6,
                "hard_blocker_count": 5,
                "top_blocker_id": "placeholder_packet_rows",
                "next_required_step": "Close packet evidence.",
            }
        },
        {
            "summary": {
                "blocked_row_count": 12,
                "ready_row_count": 0,
                "workbook_row_count": 12,
                "most_common_missing_field": "replacement_ligand_id",
                "next_required_step": "Fill CA2 rows.",
            }
        },
        {
            "summary": {
                "blocked_row_count": 6,
                "ready_for_apply_row_count": 8,
                "queue_row_count": 14,
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
                "next_required_step": "Fill PXR rows.",
            }
        },
        {
            "summary": {
                "broader_promotion_blocked": True,
                "operator_scope_now": "one_wider_shadow_safe_lane_only",
                "status": "one_wider_shadow_safe_lane_admitted_not_commercialized",
                "blocking_target": "commercialization_boundary",
                "next_required_step": "Keep bounded shadow lane only.",
            }
        },
    )

    summary = payload["summary"]
    assert summary["delivery_claim_unchanged"] is True
    assert summary["lane_count"] == 6
    assert summary["blocked_lane_count"] == 6
    assert summary["top_priority_lane_id"] == "gpcr_scaleup_ci_low"

    rows = {row["lane_id"]: row for row in payload["rows"]}
    assert rows["gpcr_scaleup_ci_low"]["positive_coverage_gap"] == 3
    assert rows["gpcr_scaleup_ci_low"]["top20_missing_positives"] == "pindolol"
    assert rows["gpcr_scaleup_ci_low"]["claim_promotion_allowed"] is False
    assert rows["pde_translation_quality"]["blocker_count"] == 5
    assert rows["transporter_aqp1_glut1_evidence"]["primary_blocker"] == "placeholder_packet_rows"
    assert rows["ca2_packet_replacement"]["policy_status"] == "blocked_prep_only"
    assert rows["pxr_packet_fill"]["primary_blocker"] == "replacement_reference_binding_kcal_mol"
    assert rows["idp_broader_promotion"]["claim_scope"] == "one_wider_shadow_safe_lane_only"


def test_gpcr_rollup_distinguishes_launch_ready_from_claim_review_blocked() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ci_low_blocker": True,
                "ranking_pr_auc_ci_low": 0.128,
                "threshold": 0.45,
                "ranking_positive_count": 6,
                "ranking_topk_hit_rate": 0.25,
            },
            "rank_diagnostics": {"top20_hit_rate_max_possible": 0.3, "top20_missing_positives": []},
            "claim_coverage_requirement": {
                "ci_low_policy": {"status": "blocked"},
            },
        },
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        gpcr_positive_coverage={"summary": {"frozen": True, "positive_count": 9}},
        gpcr_guarded_100k_readiness={
            "summary": {
                "launch_eligible": True,
                "launch_blockers": [],
                "eligible": False,
                "claim_review_eligible": False,
                "blocker_count": 4,
                "blockers": ["ci_low_below_threshold"],
                "next_required_step": "Launch a guarded 100k rerun candidate.",
            }
        },
    )

    row = payload["rows"][0]
    assert row["primary_blocker"] == "guarded_100k_claim_review_blocked"
    assert row["positive_coverage_gap"] == 0
    assert row["guarded_100k_rerun_ready"] is True
    assert row["guarded_100k_claim_review_ready"] is False
    assert row["full_100k_guarded_rerun_eligible"] is True


def test_rollup_moves_top_priority_past_gpcr_when_guarded_claim_review_is_green() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ci_low_blocker": False,
                "ranking_pr_auc_ci_low": 0.675,
                "threshold": 0.45,
                "ranking_positive_count": 13,
                "ranking_topk_hit_rate": 0.6,
            },
            "rank_diagnostics": {"top20_hit_rate_max_possible": 0.65, "top20_missing_positives": []},
            "claim_coverage_requirement": {
                "ci_low_policy": {"status": "meets_threshold"},
            },
        },
        {
            "summary": {
                "claim_promotion_allowed": False,
                "primary_blocker": "binding_energy_proxy_too_weak_for_translation",
                "failed_evidence_count": 1,
                "measurement_gap_count": 1,
                "next_required_step": "Close PDE translation-quality evidence.",
            }
        },
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        gpcr_positive_coverage={"summary": {"frozen": True, "positive_count": 13}},
        gpcr_guarded_100k_readiness={
            "summary": {
                "launch_eligible": True,
                "eligible": True,
                "claim_review_eligible": True,
                "blocker_count": 0,
                "blockers": [],
                "next_required_step": "Refresh scorecard and repeat evidence.",
            }
        },
    )

    summary = payload["summary"]
    gpcr_row = payload["rows"][0]
    assert gpcr_row["status"] == "internal_review"
    assert gpcr_row["blocker_count"] == 0
    assert gpcr_row["primary_blocker"] == "claim_locked_scorecard_refresh_repeat_required"
    assert summary["top_priority_lane_id"] == "pde_translation_quality"
    assert summary["top_priority_primary_blocker"] == "binding_energy_proxy_too_weak_for_translation"
    assert summary["evidence_blocked_lane_count"] == 2
    assert "GPCR guarded 100k evidence is green" in summary["next_required_step"]


def test_gpcr_rollup_prioritizes_trajectory_storage_gap_before_claim_review() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "ci_low_blocker": True,
                "ranking_pr_auc_ci_low": 0.128,
                "threshold": 0.45,
                "ranking_positive_count": 9,
                "ranking_topk_hit_rate": 0.25,
            },
            "rank_diagnostics": {"top20_hit_rate_max_possible": 0.3, "top20_missing_positives": []},
            "claim_coverage_requirement": {"ci_low_policy": {"status": "blocked"}},
        },
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        {"summary": {}},
        gpcr_positive_coverage={"summary": {"frozen": True, "positive_count": 9}},
        gpcr_guarded_100k_readiness={
            "summary": {
                "launch_eligible": True,
                "claim_review_eligible": False,
                "blocker_count": 3,
                "blockers": ["ci_low_below_threshold"],
                "next_required_step": "Launch a guarded 100k rerun candidate.",
            }
        },
        gpcr_trajectory_storage_gap={
            "summary": {
                "drd2_repair_blocked": True,
                "blocker_count": 4,
                "blockers": ["stage2_trajectory_frames_missing", "repair_slice_source_npz_missing"],
                "stage2_missing_run_count": 1,
                "repair_slice_npz_missing_count": 6,
                "repair_slice_unique_npz_count": 6,
                "positive_trajectory_npz_exists": False,
                "next_required_step": "Restore stage2 trajectory frames before DRD2 repair.",
            }
        },
    )

    row = payload["rows"][0]
    summary = payload["summary"]
    assert row["primary_blocker"] == "gpcr_frozen_trajectory_storage_gap"
    assert row["drd2_repair_blocked"] is True
    assert row["repair_slice_npz_missing_count"] == 6
    assert row["trajectory_gap_source_artifact"] == "runs/gpcr_frozen_trajectory_storage_gap_packet_current.json"
    assert "Restore stage2 trajectory frames" in row["next_required_step"]
    assert "Restore frozen GPCR trajectory storage" in summary["next_required_step"]


def test_render_markdown_contains_claim_boundary() -> None:
    payload = {
        "summary": {
            "delivery_claim_unchanged": True,
            "current_delivery_claim_scope": "restricted_kinase_ion_channel_gpcr",
            "blocked_lane_count": 1,
            "top_priority_lane_id": "gpcr_scaleup_ci_low",
            "top_priority_primary_blocker": "ranking_pr_auc_ci_low_positive_coverage",
            "next_required_step": "Close GPCR first.",
        },
        "rows": [
            {
                "priority_rank": 0,
                "lane_id": "gpcr_scaleup_ci_low",
                "status": "blocked",
                "claim_promotion_allowed": False,
                "primary_blocker": "ranking_pr_auc_ci_low_positive_coverage",
                "source_artifact": "runs/gpcr_ci_low_recovery_packet_current.json",
                "next_required_step": "Add coverage.",
            }
        ],
    }

    markdown = mod.render_markdown(payload)

    assert "delivery_claim_unchanged" in markdown
    assert "`gpcr_scaleup_ci_low`" in markdown
    assert "`false`" in markdown
