from __future__ import annotations

from tools import build_family_expansion_status_rollup as mod

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


def test_build_family_expansion_status_rollup_carries_aqp1_transporter_signal() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "source_linked_count": 6,
                "pending_capture_count": 0,
                "direct_negative_evidence_count": 1,
                "direct_conflict_row_count": 5,
                "no_direct_negative_found_count": 0,
                "next_required_step": "freeze ca2",
            }
        },
        {"summary": {"confirmed_manual_commit_count": 1}},
        {
            "summary": {
                "source_linked_count": 4,
                "pending_capture_count": 0,
                "supportive_target_specific_human_count": 2,
            }
        },
        {
            "summary": {
                "ready_for_apply_row_count": 1,
                "binder_gap_count": 1,
                "defer_row_count": 3,
                "next_required_step": "close pxr",
            }
        },
        {
            "summary": {
                "source_linked_count": 0,
                "pending_capture_count": 0,
                "supportive_target_specific_packet_evidence_count": 0,
            }
        },
        {
            "summary": {
                "current_phase": "blocker_closure_seed_row_promotion",
                "ready_for_apply_rows": 0,
                "placeholder_driven_rows": 9,
                "staged_non_authoritative_rows": 3,
                "aqp1_exact_human_activity_count": 1,
                "aqp1_quantitative_provenance_focus_ligand": "AqB013",
                "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                "next_required_step": "carry aqp1 provenance forward",
            }
        },
        {
            "summary": {
                "source_linked_count": 0,
                "pending_capture_count": 0,
                "supportive_direct_quantitative_binding_count": 0,
                "kcal_overlay_ready_count": 0,
            }
        },
        {
            "summary": {
                "quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
                "remaining_unresolved_fields": "replacement_reference_binding_kcal_mol",
                "next_required_step": "keep kcal blank",
            }
        },
        {
            "summary": {
                "primary_focus_ligand": "bacopaside II",
                "exact_human_reference_ligand": "AqB013",
                "next_required_step": "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank.",
            }
        },
        {
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
            }
        },
        {
            "summary": {
                "exact_human_aqp1_activity_count": 1,
                "primary_focus_ligand": "AqB013",
                "signal": "exact_human_activity_present_leave_kcal_blank",
                "next_required_step": "carry exact human provenance",
            }
        },
        {
            "summary": {
                "highest_gap_family": "transporter",
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
                "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                "aqp1_operator_provenance_note": "AqB013 carries exact human AQP1 target-activity provenance, but replacement_reference_binding_kcal_mol stays blank until claim-safe quantitative binding is curated.",
            }
        },
        aqp1_follow_on_blocker_decomposition={
            "summary": {
                "blocker_row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "exact_human_nonbinding_count": 1,
                "exact_target_pair_absent_count": 1,
                "high_or_medium_potential_count": 1,
                "claim_safe_kcal_ready_count": 0,
                "source_confirmation_primary_focus_ligand": "bacopaside II",
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False",
                "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.",
                "blocker_decomposition_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.json",
            }
        },
        local_engine_commercialization_queue=LOCAL_ENGINE_COMMERCIALIZATION_QUEUE,
    )

    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    aqp1_row = next(row for row in payload["rows"] if row["family"] == "aqp1")

    assert payload["summary"]["highest_gap_family"] == "transporter"
    assert payload["summary"]["aqp1_exact_human_activity_count"] == 1
    assert payload["summary"]["aqp1_first_wave_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert payload["summary"]["aqp1_first_wave_source_confirmation_exact_human_reference_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_first_wave_source_confirmation_signal"] == (
        "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."
    )
    assert payload["summary"]["aqp1_first_wave_follow_on_packet_ready"] is True
    assert payload["summary"]["aqp1_first_wave_follow_on_packet_row_count"] == 2
    assert payload["summary"]["aqp1_first_wave_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert payload["summary"]["aqp1_first_wave_follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.json"
    assert payload["summary"]["aqp1_first_wave_follow_on_packet_signal"] == (
        "Surface runs/aqp1_first_wave_follow_on_packet_current.json next as the 2-row AQP1 first-wave follow-on packet so transporter/AQP1 wording keeps core_binder_02, core_binder_03 in source-only follow-on staging."
    )
    assert payload["summary"]["aqp1_follow_on_blocker_decomposition_ready"] is True
    assert payload["summary"]["aqp1_follow_on_blocker_count"] == 2
    assert payload["summary"]["aqp1_follow_on_exact_human_nonbinding_count"] == 1
    assert payload["summary"]["aqp1_follow_on_exact_target_pair_absent_count"] == 1
    assert payload["summary"]["aqp1_follow_on_high_or_medium_potential_count"] == 1
    assert payload["summary"]["aqp1_follow_on_claim_safe_kcal_ready_count"] == 0
    assert payload["summary"]["aqp1_follow_on_source_confirmation_primary_focus_ligand"] == "bacopaside II"
    assert payload["summary"]["aqp1_follow_on_exact_human_guardrail_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_follow_on_blocking_signal"] == "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False"
    assert payload["summary"]["aqp1_follow_on_next_required_step"].startswith("Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail")
    assert payload["summary"]["aqp1_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.json"
    assert payload["summary"]["aqp1_quantitative_provenance_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_quantitative_provenance_signal"] == "exact_human_activity_present_leave_kcal_blank"
    assert "AqB013 carries exact human AQP1 target-activity provenance" in payload["summary"]["aqp1_operator_provenance_note"]
    assert payload["summary"]["local_engine_commercialization_queue_ready"] is True
    assert payload["summary"]["local_engine_commercialization_queue_artifact"] == "runs/local_engine_commercialization_queue_current.md"
    assert payload["summary"]["local_engine_commercialization_queue_top_priority_id"] == "nightly_reliability"
    assert payload["summary"]["local_engine_commercialization_queue_blocked_count"] == 2
    assert "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet" in payload["summary"]["next_required_step"]
    assert "Surface runs/aqp1_first_wave_follow_on_packet_current.json next as the 2-row AQP1 first-wave follow-on packet" in payload["summary"]["next_required_step"]
    assert "Follow the AQP1 follow-on blocker decomposition packet next" in payload["summary"]["next_required_step"]
    assert "core_binder_02" in payload["summary"]["next_required_step"]
    assert "core_binder_03" in payload["summary"]["next_required_step"]
    assert "keep AqB013 as the exact-human-activity reference row" in payload["summary"]["next_required_step"]
    assert "replacement_reference_binding_kcal_mol blank" in payload["summary"]["next_required_step"]
    assert "Raise engine commercialization first" in payload["summary"]["next_required_step"]
    assert "viewer mesh/canvas gap" in payload["summary"]["next_required_step"]
    assert "aqp1_first_wave_primary_focus=bacopaside II" in transporter_row["blocking_signal"]
    assert "aqp1_first_wave_exact_human_reference=AqB013" in transporter_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_ready=True" in transporter_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_artifact=runs/aqp1_first_wave_follow_on_packet_current.json" in transporter_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_targets=core_binder_02, core_binder_03" in transporter_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_row_count=2" in transporter_row["blocking_signal"]
    assert "aqp1_exact_human_activity_count=1" in transporter_row["blocking_signal"]
    assert "aqp1_focus_ligand=AqB013" in transporter_row["blocking_signal"]
    assert "aqp1_signal=exact_human_activity_present_leave_kcal_blank" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_decomposition_ready=True" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_count=2" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_exact_human_nonbinding_count=1" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_exact_target_pair_absent_count=1" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_high_or_medium_potential_count=1" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_claim_safe_kcal_ready_count=0" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_source_confirmation_primary_focus_ligand=bacopaside II" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_exact_human_guardrail_ligand=AqB013" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_blocking_signal=follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_next_required_step=Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail" in transporter_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_decomposition_artifact=runs/aqp1_follow_on_blocker_decomposition_current.json" in transporter_row["blocking_signal"]
    assert "local_engine_top_priority=nightly_reliability" in transporter_row["blocking_signal"]
    assert "local_engine_blocked=2" in transporter_row["blocking_signal"]
    assert "carry aqp1 provenance forward" in transporter_row["next_required_step"]
    assert "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet" in transporter_row["next_required_step"]
    assert "Surface runs/aqp1_first_wave_follow_on_packet_current.json next as the 2-row AQP1 first-wave follow-on packet" in transporter_row["next_required_step"]
    assert "Follow the AQP1 follow-on blocker decomposition packet next" in transporter_row["next_required_step"]
    assert "core_binder_02" in transporter_row["next_required_step"]
    assert "core_binder_03" in transporter_row["next_required_step"]
    assert "AqB013 carries exact human AQP1 target-activity provenance" in transporter_row["next_required_step"]
    assert "Raise engine commercialization first" in transporter_row["next_required_step"]
    assert "first_wave_primary_focus=bacopaside II" in aqp1_row["blocking_signal"]
    assert "exact_human_reference=AqB013" in aqp1_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_ready=True" in aqp1_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_artifact=runs/aqp1_first_wave_follow_on_packet_current.json" in aqp1_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_targets=core_binder_02, core_binder_03" in aqp1_row["blocking_signal"]
    assert "aqp1_first_wave_follow_on_packet_row_count=2" in aqp1_row["blocking_signal"]
    assert "exact_human_activity_count=1" in aqp1_row["blocking_signal"]
    assert "focus_ligand=AqB013" in aqp1_row["blocking_signal"]
    assert "signal=exact_human_activity_present_leave_kcal_blank" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_decomposition_ready=True" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_count=2" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_exact_human_nonbinding_count=1" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_exact_target_pair_absent_count=1" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_high_or_medium_potential_count=1" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_claim_safe_kcal_ready_count=0" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_source_confirmation_primary_focus_ligand=bacopaside II" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_exact_human_guardrail_ligand=AqB013" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_blocking_signal=follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_next_required_step=Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail" in aqp1_row["blocking_signal"]
    assert "aqp1_follow_on_blocker_decomposition_artifact=runs/aqp1_follow_on_blocker_decomposition_current.json" in aqp1_row["blocking_signal"]
    assert "local_engine_top_priority=nightly_reliability" in aqp1_row["blocking_signal"]
    assert "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet" in aqp1_row["next_required_step"]
    assert "Surface runs/aqp1_first_wave_follow_on_packet_current.json next as the 2-row AQP1 first-wave follow-on packet" in aqp1_row["next_required_step"]
    assert "Follow the AQP1 follow-on blocker decomposition packet next" in aqp1_row["next_required_step"]
    assert "core_binder_02" in aqp1_row["next_required_step"]
    assert "core_binder_03" in aqp1_row["next_required_step"]
    assert "carry exact human provenance" in aqp1_row["next_required_step"]
    assert "Raise engine commercialization first" in aqp1_row["next_required_step"]


def test_build_family_expansion_status_rollup_propagates_nightly_gate_burndown() -> None:
    payload = mod.build_payload(
        {"summary": {"source_linked_count": 6, "pending_capture_count": 0, "direct_negative_evidence_count": 1, "direct_conflict_row_count": 5, "no_direct_negative_found_count": 0, "next_required_step": "freeze ca2"}},
        {"summary": {"confirmed_manual_commit_count": 1}},
        {"summary": {"source_linked_count": 4, "pending_capture_count": 0, "supportive_target_specific_human_count": 2}},
        {"summary": {"ready_for_apply_row_count": 1, "binder_gap_count": 1, "defer_row_count": 3, "next_required_step": "close pxr"}},
        {"summary": {"source_linked_count": 0, "pending_capture_count": 0, "supportive_target_specific_packet_evidence_count": 0}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion", "ready_for_apply_rows": 0, "placeholder_driven_rows": 9, "staged_non_authoritative_rows": 3, "aqp1_exact_human_activity_count": 1, "aqp1_quantitative_provenance_focus_ligand": "AqB013", "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank", "next_required_step": "carry aqp1 provenance forward"}},
        {"summary": {"source_linked_count": 0, "pending_capture_count": 0, "supportive_direct_quantitative_binding_count": 0, "kcal_overlay_ready_count": 0}},
        {"summary": {"quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing", "remaining_unresolved_fields": "replacement_reference_binding_kcal_mol", "next_required_step": "keep kcal blank"}},
        {"summary": {"primary_focus_ligand": "bacopaside II", "exact_human_reference_ligand": "AqB013", "next_required_step": "Review bacopaside II first as the AQP1 core_binder_01 exact-source scope packet, keep AqB013 as the exact-human-activity reference row, and leave replacement_reference_binding_kcal_mol blank."}},
        {"summary": {"row_count": 2, "follow_on_targets": "core_binder_02, core_binder_03"}},
        {"summary": {"exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank", "next_required_step": "carry exact human provenance"}},
        {"summary": {"highest_gap_family": "transporter", "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013", "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank", "aqp1_operator_provenance_note": "AqB013 carries exact human AQP1 target-activity provenance, but replacement_reference_binding_kcal_mol stays blank until claim-safe quantitative binding is curated."}},
        local_engine_commercialization_queue=LOCAL_ENGINE_STAGE6_GATE_QUEUE,
    )

    summary = payload["summary"]
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    assert summary["local_engine_commercialization_queue_nightly_gate_burndown_artifact"] == (
        "runs/nightly_gate_burndown_packet_current.md"
    )
    assert summary["local_engine_commercialization_queue_nightly_gate_primary_metric"] == "mean_min_distance_A"
    assert "nightly_gate_burndown_packet_current.md" in summary["next_required_step"]
    assert "nightly_gate_burndown_packet_current.md" in transporter_row["next_required_step"]


def test_build_family_expansion_status_rollup_uses_functional_kcal_surrogate_and_current_negative_burndown() -> None:
    payload = mod.build_payload(
        {"summary": {"source_linked_count": 6, "pending_capture_count": 0, "direct_negative_evidence_count": 1}},
        {"summary": {"confirmed_manual_commit_count": 1}},
        {"summary": {"source_linked_count": 4, "pending_capture_count": 0, "supportive_target_specific_human_count": 2}},
        {"summary": {"ready_for_apply_row_count": 1}},
        {"summary": {"source_linked_count": 12, "pending_capture_count": 0, "supportive_target_specific_packet_evidence_count": 6}},
        {"summary": {"current_phase": "stale_apply_status", "ready_for_apply_rows": 0, "placeholder_driven_rows": 6, "staged_non_authoritative_rows": 6}},
        {"summary": {"source_linked_count": 3, "pending_capture_count": 0, "supportive_direct_quantitative_binding_count": 0, "kcal_overlay_ready_count": 0}},
        {"summary": {"quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing"}},
        {"summary": {"primary_focus_ligand": "bacopaside II", "exact_human_reference_ligand": "AqB013"}},
        {"summary": {"row_count": 2, "follow_on_targets": "core_binder_02, core_binder_03"}},
        {"summary": {"exact_human_aqp1_activity_count": 1, "primary_focus_ligand": "AqB013", "signal": "exact_human_activity_present_leave_kcal_blank"}},
        {"summary": {"highest_gap_family": "transporter"}},
        aqp1_functional_kcal_surrogate_packet={
            "summary": {
                "functional_kcal_surrogate_ready_count": 3,
                "functional_kcal_surrogate_closure_allowed": True,
                "direct_binding_gap_still_open": True,
                "next_required_step": "Use functional surrogate only.",
            }
        },
        transporter_placeholder_burndown_queue={
            "summary": {
                "row_count": 12,
                "ready_for_apply_rows": 6,
                "placeholder_driven_rows": 0,
                "staged_non_authoritative_rows": 6,
                "next_required_step": "All transporter negative placeholder rows are evidence-curated.",
            }
        },
    )

    summary = payload["summary"]
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    aqp1_row = next(row for row in payload["rows"] if row["family"] == "aqp1")

    assert summary["aqp1_functional_kcal_surrogate_ready_count"] == 3
    assert summary["aqp1_functional_kcal_surrogate_closure_allowed"] is True
    assert summary["aqp1_direct_binding_gap_still_open"] is True
    assert transporter_row["ready_like_count"] == 6
    assert "placeholder_driven_rows=0" in transporter_row["blocking_signal"]
    assert "ready_for_apply_rows=6" in transporter_row["blocking_signal"]
    assert aqp1_row["ready_like_count"] == 3
    assert aqp1_row["supportive_count"] == 3
    assert aqp1_row["phase"] == "functional_kcal_surrogate_ready_direct_binding_gap_open"
    assert "functional_kcal_surrogate_closure_allowed=True" in aqp1_row["blocking_signal"]
