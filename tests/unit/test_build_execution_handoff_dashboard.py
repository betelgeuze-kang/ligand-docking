from __future__ import annotations

from pathlib import Path

from tools import build_execution_handoff_dashboard as mod

LOCAL_ENGINE_COMMERCIALIZATION_QUEUE = {
    "summary": {
        "local_only_mode": True,
        "row_count": 5,
        "blocked_count": 2,
        "partial_count": 1,
        "keep_green_count": 1,
        "parked_science_blocker_count": 1,
        "top_priority_id": "nightly_reliability",
        "top_priority_status": "blocked",
        "engine_blocker_count": 4,
        "science_blocker_count": 1,
        "next_required_step": (
            "Raise engine commercialization first: fix nightly reliability, close the viewer mesh/canvas gap, "
            "recover wetlab execution readiness, keep refresh reproducibility green, and leave transporter "
            "negative-evidence mining parked as a science blocker until the local engine surfaces are more trustworthy."
        ),
    },
    "rows": [
        {
            "blocker_id": "nightly_reliability",
            "status": "blocked",
            "source_signal": "latest_failed_stage=stage2_trajectory_generation",
            "next_required_action": "Stabilize nightly in two passes before treating nightly as commercial-grade.",
        },
        {
            "blocker_id": "transporter_science_blocker",
            "status": "parked",
            "source_signal": "highest_gap_family=transporter; queue_row_count=6",
            "next_required_action": (
                "Park transporter as the science-blocker lane behind the engine blockers. Keep AQP1/GLUT1 "
                "negative evidence review-only, and only reopen this queue after nightly reliability, viewer "
                "usability, and wetlab execution surfaces are promoted to a safer local commercial baseline."
            ),
        },
    ],
}

LOCAL_ENGINE_STAGE6_GATE_QUEUE = {
    "summary": {
        "local_only_mode": True,
        "row_count": 5,
        "blocked_count": 1,
        "partial_count": 2,
        "keep_green_count": 1,
        "parked_science_blocker_count": 1,
        "top_priority_id": "nightly_reliability",
        "top_priority_status": "partial",
        "engine_blocker_count": 4,
        "science_blocker_count": 1,
        "nightly_gate_burndown_ready": True,
        "nightly_gate_burndown_artifact": "runs/nightly_gate_burndown_packet_current.md",
        "nightly_gate_primary_metric": "mean_min_distance_A",
        "nightly_gate_primary_value": "2.655165582969785",
        "nightly_gate_primary_threshold": "2.5",
        "nightly_gate_primary_delta": "0.15516558296978494",
        "nightly_gate_status_line": (
            "stage2 is recovered and the nightly lane is now burning down the stage6 gate at "
            "mean_min_distance_A=2.655 versus 2.500 (+0.155 over threshold)."
        ),
        "nightly_gate_recent_transition_line": (
            "2026-04-19:stage2_trajectory_generation -> "
            "2026-04-20:stage2_trajectory_generation -> "
            "2026-04-21:stage6_operational_gate"
        ),
        "nightly_gate_recent_stage6_fail_count": 1,
        "nightly_gate_next_required_step": (
            "Keep stage2 recovered and tune the stage6 operational gate via "
            "`runs/nightly_gate_burndown_packet_current.md`: move `mean_min_distance_A` down by `0.155` "
            "from `2.655` to at most `2.500` while recent stage6 fails stay at `1/3`."
        ),
        "next_required_step": (
            "Raise engine commercialization first: keep the recovered nightly writer/import path green, use "
            "runs/nightly_gate_burndown_packet_current.md to burn down the stage6 gate for mean_min_distance_A "
            "(+0.155 over threshold), close the viewer mesh/canvas gap, recover wetlab execution readiness, "
            "keep refresh reproducibility green, and leave transporter negative-evidence mining parked as a "
            "science blocker until the local engine surfaces are more trustworthy."
        ),
    },
    "rows": [
        {
            "blocker_id": "nightly_reliability",
            "status": "partial",
            "source_signal": (
                "latest_failed_stage=stage6_operational_gate; "
                "stage6_gate_burndown_artifact=runs/nightly_gate_burndown_packet_current.md"
            ),
            "next_required_action": (
                "Hold the recovered stage2 writer/import path green, then use "
                "`runs/nightly_gate_burndown_packet_current.md` as the nightly stage6 burndown surface."
            ),
        },
        {
            "blocker_id": "transporter_science_blocker",
            "status": "parked",
            "source_signal": "highest_gap_family=transporter; queue_row_count=6",
            "next_required_action": (
                "Park transporter as the science-blocker lane behind the engine blockers. Keep AQP1/GLUT1 "
                "negative evidence review-only, and only reopen this queue after nightly reliability, viewer "
                "usability, and wetlab execution surfaces are promoted to a safer local commercial baseline."
            ),
        },
    ],
}


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def _build_payload(
    pretest_rows: list[dict[str, object]],
    aqp1_negative_primary_probe_resolution_packet: dict[str, object] | None = None,
    local_engine_commercialization_queue: dict[str, object] | None = None,
) -> dict[str, object]:
    return mod.build_payload(
        {
            "summary": {
                "pretest_ready_count": sum(1 for row in pretest_rows if row["pretest_ready"] == "yes"),
                "partial_pretest_ready_count": sum(1 for row in pretest_rows if row["pretest_ready"] == "partial"),
                "blocked_pretest_count": sum(1 for row in pretest_rows if row["pretest_ready"] == "no"),
            },
            "rows": pretest_rows,
        },
        {"summary": {"gpcr_ready_endpoint_only": True, "idp_subset_only": True, "idp_commercial_pretest_ready": True}},
        {"summary": {"sequence_count": 5}},
        {"summary": {"check_count": 5}},
        {"summary": {"handoff_row_count": 7, "review_only_row_total": 7, "defer_row_total": 5}},
        {"summary": {"binder_slot_count": 6, "pending_manual_verdict_count": 0, "completed_manual_verdict_count": 6, "placeholder_driven_rows": 12, "ready_for_apply_rows": 0}},
        {
            "summary": {
                "direct_negative_evidence_count": 1,
                "direct_conflict_row_count": 5,
                "no_direct_negative_found_count": 0,
                "source_linked_count": 6,
                "closure_mode": "review_only_conflict_closure",
                "authoritative_negative_closure_allowed": False,
                "remaining_blank_field": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {
                "row_count": 4,
                "source_linked_count": 4,
                "supportive_target_specific_human_count": 2,
                "captured_conflict_or_gap_count": 4,
                "pending_capture_count": 0,
            }
        },
        {"summary": {"source_linked_count": 0, "supportive_target_specific_packet_evidence_count": 0, "pending_capture_count": 0}},
        {"summary": {"evidence_mode": "functional_potency_staged_review_only", "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing", "remaining_unresolved_fields": "replacement_reference_binding_kcal_mol"}},
        {"summary": {"direct_quantitative_binding_candidate_count": 0}},
        {"summary": {"pending_manual_count_total": 18}},
        {"summary": {"queue_row_count": 13}},
        {"summary": {"queue_row_count": 12, "high_priority_count": 5, "count_improving_candidate_count": 5, "supportive_manual_confirmation_count": 1, "actionable_conflict_resolution_count": 2, "low_probability_conflict_count": 2}},
        {"summary": {"focus_row_count": 6, "focus_mode": "low_probability_conflict_cleanup", "primary_focus_ligand": "bexarotene", "low_probability_conflict_focus_count": 2, "rows_with_literature_candidates": 3, "rows_with_high_signal_literature_candidates": 2}},
        {"summary": {"high_signal_row_count": 2, "same_sentence_human_row_count": 1, "title_direct_nonhuman_row_count": 1, "same_sentence_row_count": 2, "review_context_row_count": 1, "target_only_row_count": 1, "no_candidate_row_count": 2}},
        {"summary": {"row_count": 2, "supportive_binder_confirmation_count": 1, "conflict_confirmation_count": 1, "primary_focus_ligand": "bexarotene"}},
        {"summary": {"row_count": 1, "primary_focus_ligand": "bexarotene", "chembl_zero_activity_count": 1, "bindingdb_exact_gap_count": 1, "quantitative_value_found_count": 0}},
        {"summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9}},
        {"summary": {"highest_gap_family": "transporter"}},
        aqp1_quantitative_binding_capture_intake={"summary": {"source_linked_count": 0, "captured_review_only_gap_count": 0, "supportive_direct_quantitative_binding_count": 0, "kcal_overlay_ready_count": 0}},
        aqp1_quantitative_provenance_packet={"summary": {"row_count": 3, "pubchem_resolved_count": 3, "chembl_exact_match_count": 2, "exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        aqp1_first_wave_source_confirmation_packet={"summary": {"row_count": 3, "primary_focus_ligand": "bacopaside II", "exact_human_reference_ligand": "AqB013", "pubchem_resolved_count": 3, "exact_pair_absent_count": 2, "exact_human_activity_reference_count": 1, "claim_safe_kcal_ready_count": 0, "next_required_step": "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."}},
        aqp1_first_wave_follow_on_packet={"summary": {"row_count": 3, "primary_focus_ligand": "AqB011", "exact_human_reference_ligand": "AqB013", "follow_on_packet_artifact": "runs/aqp1_first_wave_follow_on_packet_current.json", "signal": "Review AqB011 as the follow-on exact-source scope row, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."}},
        aqp1_follow_on_blocker_decomposition={"summary": {"blocker_row_count": 2, "follow_on_targets": "core_binder_02, core_binder_03", "primary_focus_ligand": "AqB013", "exact_human_guardrail_ligand": "AqB013", "exact_human_nonbinding_count": 1, "exact_target_pair_absent_count": 1, "high_or_medium_potential_count": 1, "claim_safe_kcal_ready_count": 0, "source_confirmation_primary_focus_ligand": "bacopaside II", "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False", "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.", "blocker_decomposition_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.json"}},
        aqp1_negative_primary_probe_resolution_packet=aqp1_negative_primary_probe_resolution_packet,
        ca2_capture_sheet={"summary": {"direct_negative_evidence_count": 1, "direct_conflict_row_count": 5, "no_direct_negative_found_count": 0, "source_linked_count": 6}},
        ca2_commit_packet={"summary": {"closure_mode": "review_only_conflict_closure", "authoritative_negative_closure_allowed": False, "remaining_blank_field": "replacement_reference_binding_kcal_mol"}},
        pxr_capture_sheet={"summary": {"row_count": 4, "review_only_candidate_count": 1}},
        pxr_commit_packet={"summary": {"confirm_now_count": 1, "must_remain_deferred_count": 3, "binder_gap_count": 1}},
        pxr_burndown_console={"summary": {"today_open_now": "ibuprofen", "must_defer_count": 3}},
        pxr_conflict_resolver_packet={"summary": {"row_count": 2, "primary_focus_ligand": "acetaminophen", "pubchem_conflict_count": 1, "title_direct_nonhuman_conflict_count": 1, "exact_human_dual_mode_conflict_count": 1, "direct_human_qhts_conflict_count": 1, "nonhuman_boundary_context_count": 1}},
        glut1_second_wave_source_confirmation_packet={"summary": {"row_count": 3, "packet_artifact": "runs/glut1_second_wave_source_confirmation_packet_current.md", "primary_focus_ligand": "cytochalasin B", "primary_confirmation_target": "core_binder_01", "direct_quantitative_binding_count": 1, "next_required_step": "Keep GLUT1 as second-wave until AQP1 core_binder_01 through core_binder_03 are parked. When widened, start with core_binder_01 (cytochalasin B) as the direct quantitative human GLUT1 binding row and leave replacement_reference_binding_kcal_mol blank."}},
        local_engine_commercialization_queue=local_engine_commercialization_queue,
    )


def test_build_execution_handoff_dashboard_surfaces_pxr_and_aqp1_counts() -> None:
    payload = _build_payload(
        [
            {
                "family": "gpcr",
                "commercialization_score": 82,
                "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked",
                "runtime_scope_now": "locked_decoy_apply_safe_endpoint_only",
                "pretest_ready": "yes",
                "primary_blocker": "100k_router_still_blocked",
                "next_required_step": "keep router blocked",
            },
            {
                "family": "non_kinase_enzyme_ca2",
                "commercialization_score": 58,
                "current_state": "binding_verification_in_progress",
                "runtime_scope_now": "authoritative_partial_rows_only",
                "pretest_ready": "partial",
                "primary_blocker": "replacement_reference_binding_kcal_mol",
                "next_required_step": "fill rows",
            },
            {
                "family": "nuclear_receptor_pxr",
                "commercialization_score": 61,
                "current_state": "review_only_conflict_or_gap_closure_in_progress",
                "runtime_scope_now": "evidence_closure_only",
                "pretest_ready": "partial",
                "primary_blocker": "local_target_specific_human_evidence_gap",
                "next_required_step": "keep only ibuprofen review-only",
            },
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ]
    )
    summary = payload["summary"]
    assert summary["run_now_count"] == 1
    assert summary["prepare_next_count"] == 2
    assert summary["manual_review_only_count"] == 1
    assert summary["aqp1_quantitative_binding_source_linked_count"] == 0
    assert summary["aqp1_quantitative_binding_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert summary["aqp1_quantitative_provenance_packet_ready"] is True
    assert summary["aqp1_quantitative_provenance_row_count"] == 3
    assert summary["aqp1_quantitative_provenance_pubchem_resolved_count"] == 3
    assert summary["aqp1_quantitative_provenance_chembl_exact_match_count"] == 2
    assert summary["aqp1_quantitative_provenance_exact_human_activity_count"] == 1
    assert summary["aqp1_quantitative_provenance_primary_focus_ligand"] == "AqB013"
    assert summary["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert summary["aqp1_first_wave_source_confirmation_packet_ready"] is True
    assert summary["aqp1_first_wave_source_confirmation_row_count"] == 3
    assert summary["aqp1_first_wave_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert summary["aqp1_first_wave_source_confirmation_exact_human_reference_ligand"] == "AqB013"
    assert summary["aqp1_first_wave_source_confirmation_pubchem_resolved_count"] == 3
    assert summary["aqp1_first_wave_source_confirmation_exact_pair_absent_count"] == 2
    assert summary["aqp1_first_wave_source_confirmation_exact_human_activity_reference_count"] == 1
    assert summary["aqp1_first_wave_source_confirmation_claim_safe_kcal_ready_count"] == 0
    assert summary["aqp1_first_wave_follow_on_packet_ready"] is True
    assert summary["aqp1_first_wave_follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.json"
    assert summary["aqp1_first_wave_follow_on_row_count"] == 3
    assert summary["aqp1_first_wave_follow_on_primary_focus_ligand"] == "AqB011"
    assert summary["aqp1_first_wave_follow_on_exact_human_reference_ligand"] == "AqB013"
    assert summary["aqp1_first_wave_follow_on_signal"] == (
        "Review AqB011 as the follow-on exact-source scope row, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."
    )
    assert summary["aqp1_follow_on_blocker_decomposition_ready"] is True
    assert summary["aqp1_follow_on_blocker_count"] == 2
    assert summary["aqp1_follow_on_exact_human_nonbinding_count"] == 1
    assert summary["aqp1_follow_on_exact_target_pair_absent_count"] == 1
    assert summary["aqp1_follow_on_high_or_medium_potential_count"] == 1
    assert summary["aqp1_follow_on_claim_safe_kcal_ready_count"] == 0
    assert summary["aqp1_follow_on_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert summary["aqp1_follow_on_exact_human_guardrail_ligand"] == "AqB013"
    assert summary["aqp1_follow_on_blocking_signal"] == "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False"
    assert summary["aqp1_follow_on_next_required_step"].startswith("Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail")
    assert summary["aqp1_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.json"
    assert summary["glut1_second_wave_source_confirmation_packet_ready"] is True
    assert summary["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert summary["glut1_second_wave_source_confirmation_packet_row_count"] == 3
    assert summary["glut1_second_wave_source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    assert "core_binder_01" in summary["glut1_second_wave_source_confirmation_packet_next_required_step"]
    assert summary["glut1_second_wave_direct_quantitative_binding_count"] == 1
    _contains_tokens(
        summary["aqp1_first_wave_source_confirmation_next_required_step"],
        "bacopaside ii",
        "aqb013",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    _contains_tokens(
        summary["next_required_step"],
        "follow the aqp1 first-wave follow-on packet next",
        "follow the aqp1 follow-on blocker decomposition packet next",
        "review aqb011 as the follow-on exact-source scope row",
        "core_binder_02",
        "core_binder_03",
        "aqb013",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "glut1",
        "cytochalasin b",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    _contains_tokens(
        summary["aqp1_operator_provenance_note"],
        "aqb013",
        "exact human aqp1 target-activity provenance",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    assert summary["evidence_acquisition_queue_ready"] is True
    assert summary["evidence_acquisition_queue_rows"] == 12
    assert summary["evidence_acquisition_high_priority_count"] == 5
    assert summary["evidence_acquisition_count_improving_candidate_count"] == 5
    assert summary["evidence_acquisition_supportive_manual_confirmation_count"] == 1
    assert summary["evidence_acquisition_actionable_conflict_resolution_count"] == 2
    assert summary["evidence_acquisition_low_probability_conflict_count"] == 2
    assert summary["evidence_investigator_packet_ready"] is True
    assert summary["evidence_investigator_focus_count"] == 6
    assert summary["evidence_investigator_focus_mode"] == "low_probability_conflict_cleanup"
    assert summary["evidence_investigator_primary_focus_ligand"] == "bexarotene"
    assert summary["evidence_investigator_low_probability_conflict_focus_count"] == 2
    assert summary["ca2_closure_mode"] == "review_only_conflict_closure"
    assert summary["ca2_direct_conflict_row_count"] == 5
    assert summary["ca2_no_direct_negative_source_row_count"] == 0
    assert summary["ca2_source_linked_count"] == 6
    assert summary["ca2_direct_negative_evidence_count"] == 1
    assert summary["pxr_unresolved_row_count"] == 4
    assert summary["pxr_source_linked_count"] == 4
    assert summary["pxr_supportive_target_specific_human_count"] == 2
    assert summary["pxr_review_only_candidate_count"] == 1
    assert summary["pxr_captured_conflict_or_gap_count"] == 4
    assert summary["pxr_confirm_now_count"] == 1
    assert summary["pxr_must_defer_count"] == 3
    assert summary["pxr_binder_gap_count"] == 1
    assert summary["pxr_today_open_now"] == "ibuprofen"
    assert summary["pxr_signal"] == "review_only_1_deferred_3_keep_human_support_explicit"
    assert summary["pxr_literature_overlay_ready"] is True
    assert summary["pxr_literature_high_signal_row_count"] == 2
    assert summary["pxr_literature_same_sentence_human_row_count"] == 1
    assert summary["pxr_literature_title_direct_nonhuman_row_count"] == 1
    assert summary["pxr_literature_same_sentence_row_count"] == 2
    assert summary["pxr_literature_review_context_row_count"] == 1
    assert summary["pxr_literature_target_only_row_count"] == 1
    assert summary["pxr_literature_no_candidate_row_count"] == 2
    assert summary["pxr_confirmation_packet_ready"] is True
    assert summary["pxr_confirmation_focus_count"] == 2
    assert summary["pxr_confirmation_supportive_binder_count"] == 1
    assert summary["pxr_confirmation_conflict_count"] == 1
    assert summary["pxr_confirmation_primary_focus_ligand"] == "bexarotene"
    assert summary["pxr_conflict_resolver_packet_ready"] is True
    assert summary["pxr_conflict_resolver_focus_count"] == 2
    assert summary["pxr_conflict_resolver_primary_focus_ligand"] == "acetaminophen"
    assert summary["pxr_conflict_resolver_pubchem_conflict_count"] == 1
    assert summary["pxr_conflict_resolver_title_direct_nonhuman_conflict_count"] == 1
    assert summary["pxr_conflict_resolver_exact_human_dual_mode_conflict_count"] == 1
    assert summary["pxr_conflict_resolver_direct_human_qhts_conflict_count"] == 1
    assert summary["pxr_conflict_resolver_nonhuman_boundary_context_count"] == 1
    assert summary["pxr_quantitative_provenance_packet_ready"] is True
    assert summary["pxr_quantitative_provenance_focus_count"] == 1
    assert summary["pxr_quantitative_provenance_primary_focus_ligand"] == "bexarotene"
    assert summary["pxr_quantitative_provenance_chembl_zero_count"] == 1
    assert summary["pxr_quantitative_provenance_bindingdb_exact_gap_count"] == 1
    assert summary["pxr_quantitative_provenance_value_found_count"] == 0
    assert summary["evidence_investigator_rows_with_literature_candidates"] == 3
    assert summary["evidence_investigator_rows_with_high_signal_literature_candidates"] == 2

    gpcr_row, ca2_row, pxr_row, transporter_row = payload["rows"]
    assert gpcr_row["priority_lane"] == "run_now"
    assert gpcr_row["extra_signal"] == "endpoint_only=True"
    assert "partial_handoff_rows=7" in ca2_row["extra_signal"]
    assert "source_linked=6" in ca2_row["extra_signal"]
    assert "direct_negative_evidence=1" in ca2_row["extra_signal"]
    assert "no_direct_negative=0" in ca2_row["extra_signal"]
    assert "unresolved_rows=4" in pxr_row["extra_signal"]
    assert "supportive_human=2" in pxr_row["extra_signal"]
    assert "review_only_candidate=1" in pxr_row["extra_signal"]
    assert "captured_conflict_or_gap=4" in pxr_row["extra_signal"]
    assert "confirm_now=1" in pxr_row["extra_signal"]
    assert "must_defer=3" in pxr_row["extra_signal"]


def test_build_execution_handoff_dashboard_surfaces_aqp1_negative_primary_probe_resolution_lane() -> None:
    payload = _build_payload(
        [
            {
                "family": "gpcr",
                "commercialization_score": 82,
                "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked",
                "runtime_scope_now": "locked_decoy_apply_safe_endpoint_only",
                "pretest_ready": "yes",
                "primary_blocker": "100k_router_still_blocked",
                "next_required_step": "keep router blocked",
            },
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ],
        aqp1_negative_primary_probe_resolution_packet={
            "summary": {
                "row_count": 1,
                "primary_probe_candidate": "sodium nitroprusside",
                "solvent_fallback_candidate": "dimethyl sulfoxide",
                "resolution_decision": "keep_review_only_no_authoritative_negative_promotion",
                "next_required_step": (
                    "Open sodium nitroprusside as the first AQP1 primary-probe follow-up lane, keep it review-only while "
                    "sodium nitroprusside has no exact human AQP1 ChEMBL target-pair activity row, and use dimethyl sulfoxide only as solvent fallback."
                ),
            }
        },
    )

    summary = payload["summary"]
    rows = {row["family"]: row for row in payload["rows"]}
    transporter_row = rows["transporter"]

    assert summary["aqp1_negative_primary_probe_resolution_ready"] is True
    assert summary["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert summary["aqp1_negative_primary_probe_resolution_row_count"] == 1
    assert summary["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert summary["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    _contains_tokens(
        summary["next_required_step"],
        "negative primary-probe-resolution handoff",
        "sodium nitroprusside",
        "review-only",
        "dimethyl sulfoxide",
    )
    _contains_tokens(
        rows["transporter"]["extra_signal"],
        "aqp1_negative_primary_probe_resolution_artifact=runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        "aqp1_negative_primary_probe_resolution_candidate=sodium nitroprusside",
        "aqp1_negative_primary_probe_resolution_solvent_fallback_candidate=dimethyl sulfoxide",
        "aqp1_negative_primary_probe_resolution_decision=keep_review_only_no_authoritative_negative_promotion",
    )
    assert "seed_rows=6" in transporter_row["extra_signal"]
    assert "phase=seed_row_blocker_closure" in transporter_row["extra_signal"]
    assert "aqp1_qbind_sources=0" in transporter_row["extra_signal"]
    assert "aqp1_qbind_signal=exact_human_activity_present_leave_kcal_blank" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_rows=3" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_pubchem_resolved=3" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_chembl_exact=2" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_exact_human_activity=1" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_focus=AqB013" in transporter_row["extra_signal"]
    assert "aqp1_quantprov_signal=exact_human_activity_present_leave_kcal_blank" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_rows=3" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_focus=bacopaside II" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_exact_human_reference=AqB013" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_pubchem_resolved=3" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_exact_pair_absent=2" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_exact_human_reference_count=1" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_claim_safe_kcal_ready=0" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_follow_on_packet_artifact=runs/aqp1_first_wave_follow_on_packet_current.json" in transporter_row["extra_signal"]
    assert "aqp1_first_wave_follow_on_signal=Review AqB011 as the follow-on exact-source scope row" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_blocker_decomposition_ready=True" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_blocker_count=2" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_exact_human_nonbinding_count=1" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_exact_target_pair_absent_count=1" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_high_or_medium_potential_count=1" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_claim_safe_kcal_ready_count=0" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_source_confirmation_primary_focus_ligand=bacopaside II" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_exact_human_guardrail_ligand=AqB013" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_blocking_signal=follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_next_required_step=Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail" in transporter_row["extra_signal"]
    assert "aqp1_follow_on_blocker_decomposition_artifact=runs/aqp1_follow_on_blocker_decomposition_current.json" in transporter_row["extra_signal"]
    assert "glut1_second_wave_source_confirmation_packet_ready=True" in transporter_row["extra_signal"]
    assert "glut1_second_wave_source_confirmation_packet_artifact=runs/glut1_second_wave_source_confirmation_packet_current.md" in transporter_row["extra_signal"]
    assert "glut1_second_wave_source_confirmation_packet_row_count=3" in transporter_row["extra_signal"]
    assert "glut1_second_wave_source_confirmation_packet_primary_focus_ligand=cytochalasin B" in transporter_row["extra_signal"]
    assert "glut1_second_wave_direct_quantitative_binding_count=1" in transporter_row["extra_signal"]
    _contains_tokens(
        transporter_row["next_required_step"],
        "follow the aqp1 first-wave follow-on packet next",
        "follow the aqp1 follow-on blocker decomposition packet next",
        "review aqb011 as the follow-on exact-source scope row",
        "core_binder_02",
        "core_binder_03",
        "aqb013",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "glut1",
        "cytochalasin b",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )
    _contains_tokens(summary["next_required_step"], "seed-row", "blocker", "closure")
    _contains_tokens(
        summary["next_required_step"],
        "bacopaside ii",
        "aqb013",
        "follow the aqp1 first-wave follow-on packet next",
        "follow the aqp1 follow-on blocker decomposition packet next",
        "core_binder_02",
        "core_binder_03",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "glut1",
        "cytochalasin b",
        "replacement_reference_binding_kcal_mol",
        "blank",
    )


def test_build_execution_handoff_dashboard_surfaces_local_engine_queue() -> None:
    payload = _build_payload(
        [
            {
                "family": "gpcr",
                "commercialization_score": 82,
                "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked",
                "runtime_scope_now": "locked_decoy_apply_safe_endpoint_only",
                "pretest_ready": "yes",
                "primary_blocker": "100k_router_still_blocked",
                "next_required_step": "keep router blocked",
            },
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ],
        local_engine_commercialization_queue=LOCAL_ENGINE_COMMERCIALIZATION_QUEUE,
    )

    summary = payload["summary"]
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")

    assert summary["local_engine_commercialization_queue_ready"] is True
    assert summary["local_engine_commercialization_queue_artifact"] == "runs/local_engine_commercialization_queue_current.md"
    assert summary["local_engine_commercialization_queue_top_priority_id"] == "nightly_reliability"
    assert summary["local_engine_commercialization_queue_top_priority_status"] == "blocked"
    assert summary["local_engine_commercialization_queue_blocked_count"] == 2
    _contains_tokens(
        summary["local_engine_commercialization_queue_blocker_note"],
        "local-only commercialization",
        "nightly reliability",
        "transporter science work stays parked",
    )
    _contains_tokens(
        transporter_row["extra_signal"],
        "local_engine_top_priority=nightly_reliability",
        "local_engine_top_status=blocked",
        "local_engine_blocked=2",
        "local_engine_parked_science=1",
    )
    _contains_tokens(
        transporter_row["next_required_step"],
        "raise engine commercialization first",
        "viewer mesh/canvas gap",
        "wetlab execution readiness",
    )
    _contains_tokens(
        summary["next_required_step"],
        "raise engine commercialization first",
        "viewer mesh/canvas gap",
        "wetlab execution readiness",
    )


def test_build_execution_handoff_dashboard_propagates_nightly_gate_burndown() -> None:
    payload = _build_payload(
        [
            {
                "family": "gpcr",
                "commercialization_score": 82,
                "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked",
                "runtime_scope_now": "locked_decoy_apply_safe_endpoint_only",
                "pretest_ready": "yes",
                "primary_blocker": "100k_router_still_blocked",
                "next_required_step": "keep router blocked",
            },
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ],
        local_engine_commercialization_queue=LOCAL_ENGINE_STAGE6_GATE_QUEUE,
    )

    summary = payload["summary"]
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    assert summary["local_engine_commercialization_queue_nightly_gate_burndown_artifact"] == (
        "runs/nightly_gate_burndown_packet_current.md"
    )
    assert summary["local_engine_commercialization_queue_nightly_gate_primary_metric"] == "mean_min_distance_A"
    _contains_tokens(
        transporter_row["next_required_step"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )
    _contains_tokens(
        summary["next_required_step"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )


def test_build_execution_handoff_dashboard_uses_blocker_closure_language_when_transporter_backlog_is_zero() -> None:
    payload = _build_payload(
        [
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ]
    )
    _contains_tokens(payload["summary"]["next_required_step"], "seed-row", "blocker", "closure")


def test_build_execution_handoff_dashboard_exposes_idp_legacy_subset_basis_as_display_signal() -> None:
    payload = _build_payload(
        [
            {
                "family": "idp",
                "commercialization_score": 70,
                "current_state": "controlled_shadow_only_commercial_pretest_ready_broader_corrected_promotion_blocked",
                "runtime_scope_now": "controlled_shadow_only_commercial_pretest",
                "pretest_ready": "yes",
                "primary_blocker": "broader_full_idp_promotion_blocked",
                "next_required_step": "keep broader promotion blocked",
            },
        ]
    )
    _contains_tokens(payload["rows"][0]["extra_signal"], "legacy_subset_basis=true", "commercial_pretest_ready=true")


def test_build_execution_handoff_dashboard_markdown_surfaces_glut1_packet_handoff(tmp_path: Path) -> None:
    payload = _build_payload(
        [
            {
                "family": "transporter",
                "commercialization_score": 32,
                "current_state": "draft_packet_external_seeded_local_evidence_blocked",
                "runtime_scope_now": "manual_review_only_draft_packets",
                "pretest_ready": "no",
                "primary_blocker": "local_evidence_and_donor_policy_blocked",
                "next_required_step": "manual review only",
            },
        ]
    )

    out_md = tmp_path / "execution_handoff_dashboard.md"
    mod._write_markdown(out_md, payload)
    text = out_md.read_text(encoding="utf-8")

    _contains_tokens(
        text,
        "glut1_second_wave_source_confirmation_packet_artifact",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "glut1_second_wave_source_confirmation_packet_primary_focus_ligand",
        "cytochalasin b",
        "glut1_second_wave_direct_quantitative_binding_count",
    )
