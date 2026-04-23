from __future__ import annotations

from tools import build_family_operator_quicklink_board as mod


def test_build_family_operator_quicklink_board_payload() -> None:
    payload = mod.build_payload(
        platform_payload={
            "rows": [
                {
                    "family": "gpcr",
                    "lane": "run_now",
                    "scope_now": "locked_decoy_apply_safe_endpoint_only",
                    "current_state": "chembl50_v4_apply_safe_endpoint_router_blocked",
                    "primary_blocker": "100k_router_still_blocked",
                    "operator_action": "Run only within endpoint scope.",
                },
                {
                    "family": "ion_channel",
                    "lane": "run_now",
                    "scope_now": "measured_noop_shadow_family",
                    "current_state": "locked_decoy_shadow_ready",
                    "primary_blocker": "none",
                    "operator_action": "Run only within noop shadow family.",
                },
                {
                    "family": "idp",
                    "lane": "run_now",
                    "scope_now": "literature_anchor_subset_rg_sasa_only",
                    "current_state": "subset_safe_now_controlled_pretest_ready",
                    "primary_blocker": "broader_full_idp_promotion_blocked",
                    "operator_action": "Run only within the bounded commercial-pretest packet.",
                },
                {
                    "family": "non_kinase_enzyme_ca2",
                    "lane": "prepare_next",
                },
            ]
        },
        catalog_payload={
            "summary": {
                "aqp1_quantitative_provenance_exact_human_activity_count": 1,
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
            },
            "rows": [
                {
                    "family": "run_now",
                    "primary_artifact": "runs/run_now_safe_command_packet_current.md",
                    "secondary_artifact": "runs/run_now_family_operator_packet_current.md",
                },
                {
                    "family": "ca2",
                    "primary_artifact": "runs/ca2_reviewer_workbench_current.md",
                    "secondary_artifact": "runs/partial_authoritative_reviewer_console_current.md",
                },
                {
                    "family": "idp",
                    "primary_artifact": "runs/idp_commercial_pretest_packet_current.md",
                    "secondary_artifact": "runs/idp_page4_manual_confirmation_console_current.md",
                },
                {
                    "family": "pxr",
                    "packet_kind": "evidence_closure",
                    "primary_artifact": "runs/pxr_reviewer_workbench_current.md",
                    "secondary_artifact": "runs/partial_authoritative_reviewer_console_current.md",
                },
                {
                    "family": "pxr",
                    "packet_kind": "capture_sheet",
                    "primary_artifact": "runs/pxr_unresolved_evidence_capture_sheet_current.md",
                    "secondary_artifact": "runs/pxr_unresolved_evidence_capture_intake_current.md",
                },
                {
                    "family": "transporter",
                    "packet_kind": "blocker_closure",
                    "primary_artifact": "runs/transporter_manual_review_quickstart_packet_current.md",
                    "secondary_artifact": "runs/transporter_operator_console_current.md",
                },
                {
                    "family": "aqp1",
                    "packet_kind": "seed_row_promotion",
                    "primary_artifact": "runs/aqp1_first_seed_row_packet_current.md",
                    "secondary_artifact": "runs/transporter_seed_row_execution_packet_current.md",
                },
                {
                    "family": "aqp1",
                    "packet_kind": "quantitative_provenance",
                    "primary_artifact": "runs/aqp1_quantitative_provenance_packet_current.md",
                    "secondary_artifact": "runs/aqp1_reviewer_workbench_current.md",
                },
            ]
        },
        partial_payload={
            "family_rows": [
                {
                    "family": "ca2",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 6,
                    "blocked_rows": 6,
                    "review_focus": "today_core_review_only_negatives",
                    "artifact_check_command": "sed -n '1,200p' runs/ca2_packet_replacement_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/ca2_evidence_closure_day_plan_current.md",
                    "reviewer_note": "Keep CA2 rows review-only.",
                },
                {
                    "family": "pxr",
                    "safe_scope_now": "authoritative_partial_rows_only",
                    "ready_rows": 8,
                    "blocked_rows": 6,
                    "review_focus": "review_only_then_defer_triage",
                    "artifact_check_command": "sed -n '1,200p' runs/pxr_packet_fill_readiness_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/pxr_evidence_closure_day_plan_current.md",
                    "reviewer_note": "Keep PXR in partial-authoritative scope.",
                },
            ]
        },
        transporter_payload={
            "summary": {"current_phase": "blocker_closure_seed_row_promotion"},
            "target_rows": [
                {
                    "target": "aqp1",
                    "wave": "first",
                    "open_first": "runs/aqp1_first_seed_row_packet_current.md",
                    "pending_manual_verdict_count": 0,
                    "review_bucket": "review_only_first_wave",
                    "operator_instruction": "Start here today.",
                },
                {
                    "target": "glut1",
                    "wave": "second",
                    "open_first": "runs/glut1_manual_verdict_packet_current.md",
                    "pending_manual_verdict_count": 0,
                    "review_bucket": "review_only_second_wave",
                    "operator_instruction": "Open after AQP1.",
                },
            ]
        },
        run_now_payload={
            "rows": [
                {
                    "family": "gpcr",
                    "artifact_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/gpcr_handoff_bundle_current.md",
                    "source_artifact": "runs/gpcr_handoff_bundle_current.md",
                    "primary_handoff_note": "Use the apply-safe endpoint only; keep router promotion blocked.",
                },
                {
                    "family": "idp",
                    "artifact_check_command": "sed -n '1,200p' runs/idp_commercial_pretest_packet_current.md",
                    "guardrail_check_command": "sed -n '1,200p' runs/idp_pretest_scope_note_current.md && printf '\\n---\\n' && sed -n '1,160p' runs/idp_broader_promotion_blocker_note_current.md",
                    "source_artifact": "runs/idp_pretest_scope_note_current.md",
                    "primary_handoff_note": "Use the bounded IDP commercial-pretest packet and keep broader promotion blocked.",
                }
            ]
        },
    )

    assert payload["summary"]["lane_count"] == 3
    assert payload["summary"]["quicklink_row_count"] == 7
    assert payload["summary"]["run_now_count"] == 3
    assert payload["summary"]["partial_authoritative_count"] == 2
    assert payload["summary"]["manual_review_count"] == 2

    rows = {(row["lane"], row["family"]): row for row in payload["rows"]}
    assert rows[("run_now", "gpcr")]["open_first_artifact"] == "runs/gpcr_handoff_bundle_current.md"
    assert rows[("run_now", "ion_channel")]["open_first_artifact"] == "runs/run_now_safe_command_packet_current.md"
    assert rows[("run_now", "idp")]["open_first_artifact"] == "runs/idp_commercial_pretest_packet_current.md"
    assert rows[("run_now", "idp")]["open_first_command"] == "sed -n '1,220p' runs/idp_commercial_pretest_packet_current.md"
    assert rows[("run_now", "idp")]["guardrail_artifact"] == "runs/idp_page4_manual_confirmation_console_current.md"
    assert rows[("run_now", "idp")]["guardrail_command"] == "sed -n '1,220p' runs/idp_page4_manual_confirmation_console_current.md"
    assert rows[("partial_authoritative", "ca2")]["guardrail_artifact"] == "runs/partial_authoritative_reviewer_console_current.md"
    assert rows[("partial_authoritative", "pxr")]["open_first_artifact"] == "runs/pxr_reviewer_workbench_current.md"
    assert rows[("manual_review", "aqp1")]["guardrail_artifact"] == "runs/transporter_operator_console_current.md"
    assert rows[("manual_review", "aqp1")]["scope_now"] == "blocker_closure_seed_row_promotion_only"
    assert rows[("manual_review", "aqp1")]["primary_blocker"] == "placeholder_packet_rows_and_donor_policy_blocked"
    assert "runs/aqp1_quantitative_provenance_packet_current.md" in rows[("manual_review", "aqp1")]["open_first_command"]
    assert "runs/aqp1_reviewer_workbench_current.md" in rows[("manual_review", "aqp1")]["open_first_command"]
    assert "exact_human_activity=1" in rows[("manual_review", "aqp1")]["status_signal"]
    assert "focus=AqB013" in rows[("manual_review", "aqp1")]["status_signal"]
    assert "AqB013" in rows[("manual_review", "aqp1")]["one_line_note"]
