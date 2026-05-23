from __future__ import annotations

from tools import build_commercialization_readiness_report as mod

GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET = {
    "summary": {
        "row_count": 3,
        "primary_focus_ligand": "cytochalasin B",
        "direct_quantitative_binding_count": 1,
        "exact_target_pair_activity_count": 2,
        "structured_pair_absent_count": 1,
    }
}

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
            "source_signal": "latest_failed_stage=stage2_trajectory_generation; recent_fail_count=3/3",
            "next_required_action": "Stabilize nightly in two passes before treating nightly as commercial-grade.",
        },
        {
            "blocker_id": "transporter_science_blocker",
            "status": "parked",
            "source_signal": "highest_gap_family=transporter; queue_row_count=6; top_target_id=AQP1",
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
            "source_signal": "highest_gap_family=transporter; queue_row_count=6; top_target_id=AQP1",
            "next_required_action": (
                "Park transporter as the science-blocker lane behind the engine blockers. Keep AQP1/GLUT1 "
                "negative evidence review-only, and only reopen this queue after nightly reliability, viewer "
                "usability, and wetlab execution surfaces are promoted to a safer local commercial baseline."
            ),
        },
    ],
}

LOCAL_ENGINE_CLEAR_QUEUE = {
    "summary": {
        "local_only_mode": True,
        "row_count": 5,
        "blocked_count": 0,
        "partial_count": 0,
        "keep_green_count": 5,
        "parked_science_blocker_count": 0,
        "queue_clear": True,
        "top_priority_id": "nightly_reliability",
        "top_priority_status": "keep_green",
        "next_required_step": "Commercialization queue is clear for the current local-delivery scope.",
    },
    "rows": [],
}

WETLAB_EXECUTION_READINESS_QUEUE = {
    "summary": {
        "queue_ready": True,
        "queue_artifact": "runs/wetlab_execution_readiness_queue_current.md",
        "row_count": 5,
        "blocked_count": 3,
        "partial_count": 1,
        "ready_count": 1,
        "primary_watch_liveness": "stale",
        "antitarget_watch_liveness": "detached",
        "watch_gap_count": 2,
        "execution_ready_now_row_count": 0,
        "antitarget_ready_now_row_count": 1,
        "ready_to_send_track_count": 5,
        "selected_allatom_wetlab_gate_pass": False,
        "selected_allatom_block_reason": (
            "translation/commercial hard gate failed, translation gate failed, "
            "failed metrics: mean_min_distance_A, missing metrics: claim_gate_required_unavailable"
        ),
        "status_line": (
            "send=5 ready | primary_exec=0 ready_now (stale) | "
            "antitarget_exec=1 ready_now (detached) | selected_allatom=fail"
        ),
        "next_required_step": (
            "Recover the stale/detached watch loops, create at least one primary execution-ready row, "
            "and clear the selected all-atom wetlab gate before calling wetlab commercially execution-ready."
        ),
    },
    "rows": [
        {
            "queue_rank": 1,
            "lane_id": "primary_dispatch_lane",
            "status": "blocked",
            "signal": "primary_ready_now=0; primary_watch=stale",
            "next_required_action": (
                "Create at least one execution-ready primary row before treating wetlab as commercially dispatchable."
            ),
        }
    ],
}

WETLAB_EXECUTION_CLEAR_QUEUE = {
    "summary": {
        "queue_ready": True,
        "queue_artifact": "runs/wetlab_execution_readiness_queue_current.md",
        "row_count": 5,
        "blocked_count": 0,
        "partial_count": 0,
        "ready_count": 5,
        "primary_watch_liveness": "attached",
        "antitarget_watch_liveness": "attached",
        "watch_gap_count": 0,
        "execution_ready_now_row_count": 0,
        "antitarget_ready_now_row_count": 1,
        "ready_to_send_track_count": 5,
        "selected_allatom_wetlab_gate_pass": True,
        "top_priority_lane_id": "primary_dispatch_lane",
        "top_priority_status": "ready",
        "status_line": "send=5 ready | selected_allatom=pass",
        "next_required_step": "Wetlab execution readiness is green for the current local-delivery scope.",
    },
    "rows": [],
}

TRANSPORTER_PLACEHOLDER_ACCOUNTING_CLOSED = {
    "summary": {
        "queue_row_count": 12,
        "placeholder_driven_rows": 0,
        "ready_for_apply_rows": 6,
        "top_blocker_id": "placeholder_packet_rows",
    }
}

AQP1_FUNCTIONAL_SURROGATE_ACCOUNTING_CLOSED = {
    "summary": {
        "functional_kcal_surrogate_ready_count": 3,
        "functional_kcal_surrogate_closure_allowed": True,
        "direct_binding_gap_still_open": True,
    }
}


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_commercialization_readiness_report() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {
            "summary": {
                "status": "operator_packet_ready",
                "blocker_reason": "broader promotion blocked by corrected-path fragility",
            }
        },
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "placeholder_driven_rows": 9, "blocked_donor_check_count": 3}},
        aqp1_follow_on_blocker_decomposition={
            "summary": {
                "blocker_row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
                "primary_focus_ligand": "AqB013",
                "exact_human_guardrail_ligand": "AqB013",
                "exact_human_nonbinding_count": 1,
                "exact_target_pair_absent_count": 1,
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False",
                "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.",
            }
        },
        glut1_second_wave_source_confirmation_packet=GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET,
        local_engine_commercialization_queue=LOCAL_ENGINE_COMMERCIALIZATION_QUEUE,
        wetlab_execution_readiness_queue=WETLAB_EXECUTION_READINESS_QUEUE,
    )

    assert payload["summary"]["family_count"] == 7
    assert payload["summary"]["core_commercial_lane_score"] == 82.5
    assert payload["summary"]["all_category_expansion_score"] == 68.9
    families = {row["family"] for row in payload["rows"]}
    assert "gpcr" in families
    assert "transporter" in families
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["status"] == "controlled_shadow_only_commercial_pretest_ready_broader_blocked"
    _contains_tokens(rows["idp"]["claim_safe_scope"], "controlled", "commercial-pretest", "subset", "basis")
    assert rows["idp"]["source_artifact"] == "runs/idp_commercial_pretest_packet_current.md"
    assert rows["transporter"]["status"] == "manual_verdict_complete_blocker_closure_seed_row_promotion"
    assert rows["transporter"]["source_artifact"] == "runs/transporter_commercialization_closure_queue_current.md"
    _contains_tokens(rows["transporter"]["primary_blocker"], "top_queue_id=seed_core_binder_01", "placeholder_driven_rows=9", "blocked_donor_check_count=3")
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_row_count"] == 2
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count"] == 1
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count"] == 1
    _contains_tokens(payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal"], "authoritative_apply_allowed=False", "exact_human_guardrail=AqB013")
    _contains_tokens(payload["summary"]["next_required_step"], "follow-on blocker decomposition", "core_binder_02", "core_binder_03", "aqb013")
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_rows"] == 3
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    assert payload["summary"]["glut1_second_wave_direct_quantitative_binding_count"] == 1
    assert payload["summary"]["local_engine_commercialization_queue_ready"] is True
    assert payload["summary"]["local_engine_commercialization_queue_artifact"] == "runs/local_engine_commercialization_queue_current.md"
    assert payload["summary"]["local_engine_commercialization_queue_top_priority_id"] == "nightly_reliability"
    assert payload["summary"]["local_engine_commercialization_queue_blocked_count"] == 2
    assert payload["summary"]["wetlab_execution_readiness_queue_ready"] is True
    assert payload["summary"]["wetlab_execution_readiness_queue_json"] == "runs/wetlab_execution_readiness_queue_current.json"
    assert payload["summary"]["wetlab_execution_readiness_queue_csv"] == "runs/wetlab_execution_readiness_queue_current.csv"
    assert payload["summary"]["wetlab_execution_readiness_queue_artifact"] == "runs/wetlab_execution_readiness_queue_current.md"
    assert payload["summary"]["wetlab_execution_readiness_queue_top_priority_lane_id"] == "primary_dispatch_lane"
    assert payload["summary"]["wetlab_execution_readiness_queue_top_priority_status"] == "blocked"
    _contains_tokens(
        payload["summary"]["local_engine_commercialization_queue_blocker_note"],
        "local-only commercialization",
        "nightly reliability",
        "transporter science work stays parked",
    )
    _contains_tokens(
        payload["summary"]["wetlab_execution_readiness_queue_blocker_note"],
        "runs/wetlab_execution_readiness_queue_current.md",
        "primary dispatch lane",
        "selected all-atom gate is failing",
    )
    _contains_tokens(
        payload["summary"]["main_platform_story"],
        "glut1 second-wave source-confirmation packet handoff",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "runs/local_engine_commercialization_queue_current.md",
        "nightly reliability",
        "runs/wetlab_execution_readiness_queue_current.md",
        "primary dispatch lane",
    )
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "glut1 second-wave source-confirmation packet handoff",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
        "raise engine commercialization first",
        "viewer mesh/canvas gap",
        "selected all-atom wetlab gate",
    )


def test_build_commercialization_readiness_report_prefers_idp_commercial_decision() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {"summary": {"status": "operator_packet_ready", "blocker_reason": "packet blocker"}},
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "placeholder_driven_rows": 9, "blocked_donor_check_count": 3}},
        {
            "summary": {
                "status": "controlled_shadow_only_commercial_pretest_completed_shadow_safe",
                "operator_scope_now": "controlled_shadow_only_commercial_pretest",
                "blocker_reason": "tau_k18 fragility",
                "same_scope_reproducibility_confirmed": True,
                "additional_anchor_backed_target_count": 0,
                "page4_candidate_ready_now": True,
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
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False",
                "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.",
            }
        },
        glut1_second_wave_source_confirmation_packet=GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET,
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["idp"]["status"] == "controlled_shadow_only_commercial_pretest_completed_shadow_safe"
    assert rows["idp"]["source_artifact"] == "runs/idp_commercial_pretest_decision_current.md"
    assert rows["idp"]["primary_blocker"] == "tau_k18 fragility"
    _contains_tokens(payload["summary"]["next_required_step"], "page4", "quantitative", "anchor", "replacement")
    _contains_tokens(payload["summary"]["next_required_step"], "aqp1", "core_binder_01", "aqb013")
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_ready"] is True
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["glut1_second_wave_source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "glut1 second-wave source-confirmation packet handoff",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
    )


def test_build_commercialization_readiness_report_surfaces_follow_on_lane() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {"summary": {"status": "operator_packet_ready", "blocker_reason": "packet blocker"}},
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "placeholder_driven_rows": 9, "blocked_donor_check_count": 3}},
        aqp1_source_confirmation_packet={
            "summary": {
                "primary_focus_ligand": "bacopaside II",
                "exact_human_reference_ligand": "AqB013",
                "claim_safe_kcal_ready_count": 0,
            }
        },
        aqp1_follow_on_packet={
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
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
                "blocking_signal": "follow_on_targets=core_binder_02, core_binder_03; exact_human_guardrail=AqB013; exact_human_nonbinding=1; exact_target_pair_absent=1; authoritative_apply_allowed=False",
                "next_required_step": "Keep core_binder_02 (AqB013) as the exact-human-activity follow-on guardrail with replacement_reference_binding_kcal_mol blank, keep core_binder_03 (AqB011) deferred until exact target-pair evidence is curated, and do not widen to GLUT1 until both follow-on blockers are explicitly parked.",
            }
        },
        glut1_second_wave_source_confirmation_packet=GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET,
    )
    summary = payload["summary"]
    rows = {row["family"]: row for row in payload["rows"]}
    assert summary["aqp1_first_wave_follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert summary["aqp1_first_wave_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_first_wave_follow_on_lane_label"] == "core_binder_02/03"
    assert summary["aqp1_first_wave_follow_on_row_count"] == 2
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_row_count"] == 2
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand"] == "AqB013"
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand"] == "AqB013"
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count"] == 1
    assert summary["aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count"] == 1
    _contains_tokens(summary["aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal"], "authoritative_apply_allowed=False", "exact_human_guardrail=AqB013")
    _contains_tokens(summary["aqp1_first_wave_follow_on_blocker_decomposition_next_required_step"], "core_binder_02", "guardrail", "core_binder_03", "target-pair")
    _contains_tokens(summary["next_required_step"], "core_binder_01", "core_binder_02/03", "aqb013 exact human", "follow-on")
    assert summary["glut1_second_wave_source_confirmation_packet_ready"] is True
    assert summary["glut1_second_wave_source_confirmation_packet_artifact"] == "runs/glut1_second_wave_source_confirmation_packet_current.md"
    assert summary["glut1_second_wave_source_confirmation_packet_rows"] == 3
    assert summary["glut1_second_wave_source_confirmation_packet_primary_focus_ligand"] == "cytochalasin B"
    assert summary["glut1_second_wave_direct_quantitative_binding_count"] == 1
    _contains_tokens(
        summary["main_platform_story"],
        "glut1 second-wave source-confirmation packet handoff",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
    )
    _contains_tokens(
        summary["next_required_step"],
        "glut1 second-wave source-confirmation packet handoff",
        "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "cytochalasin b",
    )
    _contains_tokens(rows["transporter"]["claim_safe_scope"], "bacopaside ii", "aqb013", "core_binder_02/03", "follow-on aqp1 lane")


def test_build_commercialization_readiness_report_surfaces_negative_primary_probe_resolution_lane() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {"summary": {"status": "operator_packet_ready", "blocker_reason": "packet blocker"}},
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "placeholder_driven_rows": 9, "blocked_donor_check_count": 3}},
        aqp1_source_confirmation_packet={
            "summary": {
                "primary_focus_ligand": "bacopaside II",
                "exact_human_reference_ligand": "AqB013",
                "claim_safe_kcal_ready_count": 0,
            }
        },
        aqp1_follow_on_packet={
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
            }
        },
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
        glut1_second_wave_source_confirmation_packet=GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET,
    )

    summary = payload["summary"]
    assert summary["aqp1_negative_primary_probe_resolution_ready"] is True
    assert summary["aqp1_negative_primary_probe_resolution_artifact"] == "runs/aqp1_negative_primary_probe_resolution_packet_current.md"
    assert summary["aqp1_negative_primary_probe_resolution_row_count"] == 1
    assert summary["aqp1_negative_primary_probe_resolution_candidate"] == "sodium nitroprusside"
    assert summary["aqp1_negative_primary_probe_resolution_solvent_fallback_candidate"] == "dimethyl sulfoxide"
    assert summary["aqp1_negative_primary_probe_resolution_decision"] == "keep_review_only_no_authoritative_negative_promotion"
    _contains_tokens(
        summary["main_platform_story"],
        "aqp1 negative primary-probe-resolution handoff",
        "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
    )
    _contains_tokens(
        summary["next_required_step"],
        "aqp1 negative primary-probe-resolution handoff",
        "runs/aqp1_negative_primary_probe_resolution_packet_current.md",
        "sodium nitroprusside",
        "dimethyl sulfoxide",
        "review-only",
    )


def test_build_commercialization_readiness_report_propagates_nightly_gate_burndown() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {"summary": {"status": "operator_packet_ready", "blocker_reason": "packet blocker"}},
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=12; ready_for_apply_rows=0"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "placeholder_driven_rows": 9, "blocked_donor_check_count": 3}},
        glut1_second_wave_source_confirmation_packet=GLUT1_SECOND_WAVE_SOURCE_CONFIRMATION_PACKET,
        local_engine_commercialization_queue=LOCAL_ENGINE_STAGE6_GATE_QUEUE,
    )

    summary = payload["summary"]
    assert summary["local_engine_commercialization_queue_nightly_gate_burndown_artifact"] == (
        "runs/nightly_gate_burndown_packet_current.md"
    )
    assert summary["local_engine_commercialization_queue_nightly_gate_primary_metric"] == "mean_min_distance_A"
    _contains_tokens(
        summary["local_engine_commercialization_queue_blocker_note"],
        "nightly stage6 burndown packet",
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )
    _contains_tokens(
        summary["main_platform_story"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )
    _contains_tokens(
        summary["next_required_step"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
        "viewer mesh/canvas gap",
    )


def test_build_commercialization_readiness_report_closes_tracked_local_accounting() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {"summary": {"endpoint_status": "locked_decoy_apply_safe_router_blocked"}},
        {"summary": {"decision": "go_literature_anchor_default_mask_promotion"}},
        {"summary": {"status": "operator_packet_ready", "blocker_reason": "packet blocker"}},
        {"summary": {"ready_row_count": 6, "workbook_row_count": 12}},
        {"summary": {"ready_for_apply_row_count": 8, "matched_queue_rows": 14}},
        {"summary": {"current_phase": "blocker_closure_seed_row_promotion"}},
        {"summary": {"top_blocker_signal": "placeholder_driven_rows=0; ready_for_apply_rows=6"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "blocked_count": 2}},
        transporter_placeholder_burndown_queue=TRANSPORTER_PLACEHOLDER_ACCOUNTING_CLOSED,
        aqp1_functional_kcal_surrogate_packet=AQP1_FUNCTIONAL_SURROGATE_ACCOUNTING_CLOSED,
        local_engine_commercialization_queue=LOCAL_ENGINE_CLEAR_QUEUE,
        wetlab_execution_readiness_queue=WETLAB_EXECUTION_CLEAR_QUEUE,
    )

    summary = payload["summary"]
    assert summary["tracked_readiness_accounting_closed"] is True
    assert summary["transporter_placeholder_accounting_closed"] is True
    assert summary["aqp1_functional_surrogate_accounting_closed"] is True
    assert summary["wetlab_execution_readiness_queue_clear"] is True
    _contains_tokens(
        summary["main_platform_story"],
        "tracked local commercialization readiness accounting is closed",
        "direct binding kcal claims remain blank",
        "outside this closed local readiness claim",
    )
    _contains_tokens(
        summary["next_required_step"],
        "restricted local-delivery evidence",
        "post-readiness lanes",
    )
    assert "all-category commercialization is still held back" not in summary["main_platform_story"]
    assert "transporter closure queue starting" not in summary["next_required_step"]
