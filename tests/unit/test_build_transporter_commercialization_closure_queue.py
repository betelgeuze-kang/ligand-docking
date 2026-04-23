from __future__ import annotations

from tools import build_transporter_commercialization_closure_queue as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_transporter_commercialization_closure_queue() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "today_seed_target": "AQP1 core_binder_01",
                "aqp1_seed_surface_count": 3,
                "binder_row_count": 6,
                "top_blocker_signal": "placeholder_driven_rows=9; staged_non_authoritative_rows=3; ready_for_apply_rows=0",
                "next_required_step": "Work AQP1 first-wave rows before GLUT1.",
            }
        },
        {
            "summary": {
                "current_phase": "blocker_closure_seed_row_promotion",
                "placeholder_driven_rows": 9,
                "staged_non_authoritative_rows": 3,
                "binder_seed_row_count": 6,
            }
        },
        {
            "summary": {
                "review_only_negative_count": 3,
                "policy_fixed_pending_count": 6,
            },
            "rows": [
                {
                    "packet_step": "core_binder_02",
                    "suggested_external_candidate": "AqB013",
                    "public_provenance_status": "exact_human_aqp1_quantitative_activity_present_nonbinding",
                    "public_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                    "chembl_best_activity_value": "20000.0",
                    "chembl_best_activity_units": "nM",
                    "promotion_blocker": "no_claim_safe_aqp1_binding_kcal_curated",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "next_required_action": "carry_exact_human_activity_provenance_keep_kcal_blank",
                },
                {
                    "packet_step": "core_non_binder_01",
                    "promotion_blocker": "no_quantitative_transporter_negative_evidence_curated",
                    "required_missing_fields": "replacement_reference_binding_kcal_mol",
                    "next_required_action": "manual_negative_evidence_review",
                },
            ],
        },
        {
            "summary": {
                "exact_human_aqp1_activity_count": 1,
                "primary_focus_ligand": "AqB013",
                "signal": "exact_human_activity_present_leave_kcal_blank",
            }
        },
        {
            "summary": {
                "row_count": 3,
                "primary_focus_ligand": "bacopaside II",
            }
        },
        {
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "next_required_step": "After core_binder_01, use core_binder_02 (AqB013) as the first AQP1 follow-on lane, then continue core_binder_03 (AqB011) before widening to GLUT1.",
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; authoritative_apply_allowed=False",
            }
        },
        {
            "summary": {
                "row_count": 2,
                "primary_focus_ligand": "AqB013",
            }
        },
        {
            "summary": {
                "blocker_row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "exact_human_nonbinding_count": 1,
                "exact_target_pair_absent_count": 1,
                "next_required_step": "Keep core_binder_02 as the exact-human guardrail and core_binder_03 as the target-pair gap.",
            }
        },
        {
            "summary": {
                "current_phase": "blocker_closure_seed_row_promotion",
                "today_open_now": "runs/aqp1_first_seed_row_packet_current.md",
                "today_open_now_label": "bacopaside II",
                "today_open_source_confirmation": "runs/aqp1_first_wave_source_confirmation_packet_current.md",
                "today_open_provenance": "runs/aqp1_quantitative_provenance_packet_current.md",
                "today_finish_line": "Manual-verdict backlog is cleared. Use AQP1 first, then core_binder_02 and core_binder_03 before GLUT1.",
                "aqp1_follow_on_seed_targets": "core_binder_02, core_binder_03",
                "today_open_follow_on_blocker_decomposition": "runs/aqp1_follow_on_blocker_decomposition_current.md",
                "aqp1_follow_on_blocker_decomposition_artifact": "runs/aqp1_follow_on_blocker_decomposition_current.md",
                "aqp1_follow_on_blocker_decomposition_row_count": 2,
                "aqp1_follow_on_blocker_decomposition_follow_on_targets": "core_binder_02, core_binder_03",
                "aqp1_follow_on_blocker_decomposition_primary_focus_ligand": "AqB013",
                "aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand": "AqB013",
                "aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count": 1,
                "aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count": 1,
                "aqp1_follow_on_blocker_decomposition_next_required_step": "Keep core_binder_02 as the exact-human guardrail and core_binder_03 as the target-pair gap.",
            }
        },
        {
            "summary": {
                "aqp1_open_provenance": "runs/aqp1_quantitative_provenance_packet_current.md",
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
                "aqp1_quantitative_provenance_signal": "exact_human_activity_present_leave_kcal_blank",
                "aqp1_quantitative_binding_status": "quantitative_binding_absent_claim_safe_kcal_missing",
                "aqp1_remaining_unresolved_fields": "replacement_reference_binding_kcal_mol",
            }
        },
        {
            "summary": {
                "blocked_check_count": 3,
            },
            "rows": [
                {
                    "check_id": "candidate_has_non_placeholder_packet_row",
                    "ready_when": "At least one transporter binder row is no longer placeholder-driven.",
                },
                {
                    "check_id": "p0_scaffold_open_count_zero",
                    "ready_when": "Transporter P0 open count reaches 0.",
                },
            ],
        },
        {
            "summary": {
                "top_blocker_id": "placeholder_packet_rows",
            },
            "rows": [
                {
                    "blocker_id": "placeholder_packet_rows",
                    "current_signal": "placeholder_driven_rows=9; staged_non_authoritative_rows=3; ready_for_apply_rows=0",
                    "next_action": "replace placeholder-driven transporter workbook rows",
                },
                {
                    "blocker_id": "donor_policy_frozen",
                    "current_signal": "reopen_ready=False; blocked_check_count=3; fit_donor=EGFR_KINASE",
                },
            ],
        },
        {
            "summary": {
                "first_wave_target": "AQP1",
                "second_wave_target": "GLUT1",
                "decision_status": "aqp1_first_wave_glut1_second_wave",
                "next_required_step": "Keep AQP1 first-wave and GLUT1 second-wave.",
            },
            "rows": [
                {
                    "target_id": "GLUT1",
                    "wave_label": "second_wave_higher_upside",
                    "placeholder_rows": 6,
                    "p0_open_count": 5,
                    "local_evidence_status": "draft_only_local_evidence_blocked",
                }
            ],
        },
    )

    summary = payload["summary"]
    assert summary["queue_row_count"] == 6
    assert summary["top_queue_id"] == "seed_core_binder_01"
    assert summary["family_blocker_count"] == 1
    assert summary["wave_hold_count"] == 1
    assert summary["aqp1_focus_ligand"] == "AqB013"
    assert summary["blocked_donor_check_count"] == 3
    assert summary["aqp1_follow_on_packet_ready"] is True
    assert summary["aqp1_follow_on_row_count"] == 2
    assert summary["aqp1_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_open_follow_on"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert summary["aqp1_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["aqp1_follow_on_blocker_decomposition_ready"] is True
    assert summary["aqp1_follow_on_blocker_decomposition_row_count"] == 2
    assert summary["aqp1_follow_on_blocker_decomposition_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_follow_on_blocker_decomposition_primary_focus_ligand"] == "AqB013"
    assert summary["aqp1_follow_on_blocker_decomposition_exact_human_guardrail_ligand"] == "AqB013"
    assert summary["aqp1_follow_on_blocker_decomposition_exact_human_nonbinding_count"] == 1
    assert summary["aqp1_follow_on_blocker_decomposition_exact_target_pair_absent_count"] == 1
    _contains_tokens(summary["aqp1_follow_on_blocker_decomposition_next_required_step"], "core_binder_02", "guardrail", "core_binder_03", "target-pair")
    _contains_tokens(summary["aqp1_operator_provenance_note"], "AqB013", "exact human AQP1 target-activity provenance", "replacement_reference_binding_kcal_mol")
    _contains_tokens(summary["next_required_step"], "core_binder_01", "aqb013", "follow-on", "placeholder-driven", "glut1")

    rows = payload["rows"]
    assert rows[0]["queue_id"] == "seed_core_binder_01"
    assert rows[0]["lane_status"] == "active_now"
    assert rows[0]["support_artifact"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"

    provenance_row = rows[1]
    assert provenance_row["focus_label"] == "AqB013"
    assert provenance_row["next_required_action"] == "carry_exact_human_activity_provenance_keep_kcal_blank"
    _contains_tokens(
        provenance_row["closure_signal"],
        "exact_human_aqp1_quantitative_activity_present_nonbinding",
        "ic50=20000.0 nm",
        "exact_human_activity_present_leave_kcal_blank",
    )

    follow_on_row = rows[2]
    assert follow_on_row["primary_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    _contains_tokens(follow_on_row["closure_signal"], "follow_on_row_count=2", "core_binder_02, core_binder_03")
    _contains_tokens(
        follow_on_row["closure_signal"],
        "follow_on_blocker_decomposition_artifact=runs/aqp1_follow_on_blocker_decomposition_current.md",
    )
    _contains_tokens(follow_on_row["next_required_action"], "core_binder_02", "core_binder_03", "follow-on blocker decomposition", "guardrail", "target-pair")

    blocker_rows = {row["queue_id"]: row for row in rows if row["queue_type"] == "family_blocker"}
    assert "family_placeholder_burndown" in blocker_rows
    assert blocker_rows["family_placeholder_burndown"]["support_artifact"] == "runs/transporter_placeholder_burndown_queue_current.md"
    _contains_tokens(blocker_rows["family_placeholder_burndown"]["unlock_condition"], "placeholder-driven", "authoritative transporter apply")

    assert rows[-1]["queue_type"] == "wave_hold"
    assert rows[-1]["target_id"] == "GLUT1"
