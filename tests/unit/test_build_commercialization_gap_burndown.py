from __future__ import annotations

from tools import build_commercialization_gap_burndown as mod

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


def test_build_commercialization_gap_burndown(tmp_path) -> None:
    payload = mod.build_payload(
        {
            "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
            "rows": [
                {"family": "gpcr", "score": 82, "primary_blocker": "router", "source_artifact": "gpcr.md"},
                {"family": "ion_channel", "score": 88, "primary_blocker": "", "source_artifact": "ion.md"},
                {"family": "kinase", "score": 90, "primary_blocker": "", "source_artifact": "kinase.md"},
                {"family": "idp", "score": 70, "primary_blocker": "broader_full_idp_promotion_blocked", "source_artifact": "idp.md"},
                {"family": "non_kinase_enzyme_ca2", "score": 58, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "ca2.md"},
                {"family": "nuclear_receptor_pxr", "score": 62, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "pxr.md"},
                {"family": "transporter", "score": 32, "primary_blocker": "local_evidence_and_donor_policy_blocked", "source_artifact": "tx.md"},
            ],
        },
        {
            "rows": [
                {"family": "gpcr", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "endpoint", "primary_blocker": "100k_router_still_blocked", "next_required_step": "keep endpoint"},
                {"family": "ion_channel", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "kinase", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "idp", "pretest_ready": "yes", "claim_safe_test_ready": "subset_only", "current_state": "subset", "primary_blocker": "broader_full_idp_promotion_blocked", "next_required_step": "keep subset"},
                {"family": "non_kinase_enzyme_ca2", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2"},
                {"family": "nuclear_receptor_pxr", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR"},
                {"family": "transporter", "pretest_ready": "no", "claim_safe_test_ready": "no", "current_state": "blocked", "primary_blocker": "local_evidence_and_donor_policy_blocked", "next_required_step": "finish manual review"},
            ]
        },
        {"rows": []},
        {
            "summary": {
                "transporter_placeholder_driven_rows": 9,
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
                "aqp1_operator_provenance_note": "AqB013 carries exact human AQP1 target-activity provenance, but replacement_reference_binding_kcal_mol stays blank until claim-safe quantitative binding is curated.",
                "ca2_direct_conflict_row_count": 5,
                "pxr_must_defer_count": 3,
                "pxr_confirmation_primary_focus_ligand": "bexarotene",
            }
        },
        {
            "summary": {
                "queue_row_count": 8,
                "top_queue_id": "seed_core_binder_01",
                "next_required_step": "Start with AQP1 core_binder_01, carry AqB013 as the exact-human-activity provenance hold, then burn down placeholder-driven transporter rows.",
            }
        },
        {
            "summary": {
                "row_count": 3,
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
        aqp1_follow_on_blocker_decomposition_payload={
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
        local_engine_commercialization_queue_payload=LOCAL_ENGINE_COMMERCIALIZATION_QUEUE,
        wetlab_execution_readiness_queue_payload=WETLAB_EXECUTION_READINESS_QUEUE,
    )
    assert payload["summary"]["family_count"] == 7
    assert payload["summary"]["near_term_count"] == 3
    assert payload["summary"]["subset_only_count"] == 1
    assert payload["summary"]["evidence_fill_count"] == 2
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["highest_gap_family"] == "transporter"
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
    assert payload["summary"]["wetlab_execution_readiness_queue_blocked_count"] == 3
    assert payload["summary"]["transporter_placeholder_driven_rows"] == 9
    assert payload["summary"]["transporter_commercialization_closure_queue_artifact"] == "runs/transporter_commercialization_closure_queue_current.md"
    assert payload["summary"]["transporter_commercialization_closure_queue_rows"] == 8
    assert payload["summary"]["transporter_commercialization_top_queue_id"] == "seed_core_binder_01"
    assert payload["summary"]["aqp1_first_wave_source_confirmation_artifact"] == "runs/aqp1_first_wave_source_confirmation_packet_current.md"
    assert payload["summary"]["aqp1_first_wave_follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_artifact"] == "runs/aqp1_follow_on_blocker_decomposition_current.md"
    assert payload["summary"]["aqp1_first_wave_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert payload["summary"]["aqp1_first_wave_follow_on_lane_label"] == "core_binder_02/03"
    assert payload["summary"]["aqp1_first_wave_follow_on_row_count"] == 2
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_row_count"] == 2
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_primary_focus_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_guardrail_ligand"] == "AqB013"
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_human_nonbinding_count"] == 1
    assert payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_exact_target_pair_absent_count"] == 1
    _contains_tokens(payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_blocking_signal"], "authoritative_apply_allowed=False", "exact_human_guardrail=AqB013")
    _contains_tokens(
        payload["summary"]["aqp1_first_wave_follow_on_blocker_decomposition_next_required_step"],
        "core_binder_02",
        "guardrail",
        "core_binder_03",
        "target-pair",
    )
    assert payload["summary"]["aqp1_focus_ligand"] == "AqB013"
    _contains_tokens(
        payload["summary"]["next_required_step"],
        "transporter",
        "placeholder-driven",
        "aqb013",
        "core_binder_02/03",
        "follow-on blocker decomposition",
        "raise engine commercialization first",
        "viewer mesh/canvas gap",
        "selected all-atom wetlab gate",
    )
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["gpcr"]["burndown_bucket"] == "near_term"
    assert rows["idp"]["burndown_bucket"] == "subset_only"
    assert rows["non_kinase_enzyme_ca2"]["burndown_bucket"] == "evidence_fill"
    assert rows["transporter"]["burndown_bucket"] == "blocked"
    assert rows["transporter"]["commercialization_closure_queue_artifact"] == "runs/transporter_commercialization_closure_queue_current.md"
    _contains_tokens(
        rows["transporter"]["closure_signal"],
        "placeholder_rows=9",
        "aqp1_focus=aqb013",
        "queue_rows=8",
        "top_queue_id=seed_core_binder_01",
        "follow_on_targets=core_binder_02, core_binder_03",
        "follow_on_lane=core_binder_02/03",
        "follow_on_blocker_decomposition_artifact=runs/aqp1_follow_on_blocker_decomposition_current.md",
        "follow_on_blocker_decomposition_signal=follow_on_targets=core_binder_02, core_binder_03",
        "authoritative_apply_allowed=False",
        "local_engine_top_priority=nightly_reliability",
        "local_engine_blocked=2",
        "wetlab_queue_artifact=runs/wetlab_execution_readiness_queue_current.md",
        "wetlab_top_priority=primary_dispatch_lane",
        "wetlab_top_priority_signal=primary_ready_now=0, primary_watch=stale",
        "wetlab_selected_allatom_gate_pass=False",
        "wetlab_selected_allatom_block_reason=translation/commercial hard gate failed",
    )
    _contains_tokens(rows["non_kinase_enzyme_ca2"]["closure_signal"], "direct_conflicts=5")
    _contains_tokens(rows["nuclear_receptor_pxr"]["closure_signal"], "must_defer=3", "confirmation_focus=bexarotene")
    _contains_tokens(
        rows["transporter"]["next_burndown_action"],
        "aqb013",
        "exact-human-activity",
        "replacement_reference_binding_kcal_mol",
        "placeholder-driven",
        "selected all-atom wetlab gate",
        "core_binder_02/03",
        "follow-on blocker decomposition",
        "raise engine commercialization first",
        "wetlab execution readiness",
    )
    _contains_tokens(
        rows["idp"]["next_burndown_action"],
        "controlled",
        "commercial-pretest",
        "validated basis",
        "anchor-backed",
    )
    out_md = tmp_path / "commercialization_gap_burndown_current.md"
    mod._write_markdown(out_md, payload)
    markdown = out_md.read_text(encoding="utf-8")
    _contains_tokens(
        markdown,
        "wetlab_execution_readiness_queue_blocked_count: `3`",
        "wetlab_execution_readiness_queue_top_priority_signal: `primary_ready_now=0; primary_watch=stale`",
        "wetlab_execution_readiness_queue_selected_allatom_block_reason: `translation/commercial hard gate failed",
    )


def test_build_commercialization_gap_burndown_surfaces_follow_on_lane() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
            },
            "rows": [
                {"family": "gpcr", "score": 82, "primary_blocker": "router", "source_artifact": "gpcr.md"},
                {"family": "ion_channel", "score": 88, "primary_blocker": "", "source_artifact": "ion.md"},
                {"family": "kinase", "score": 90, "primary_blocker": "", "source_artifact": "kinase.md"},
                {"family": "idp", "score": 70, "primary_blocker": "broader_full_idp_promotion_blocked", "source_artifact": "idp.md"},
                {"family": "non_kinase_enzyme_ca2", "score": 58, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "ca2.md"},
                {"family": "nuclear_receptor_pxr", "score": 62, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "pxr.md"},
                {"family": "transporter", "score": 32, "primary_blocker": "local_evidence_and_donor_policy_blocked", "source_artifact": "tx.md"},
            ],
        },
        {
            "rows": [
                {"family": "gpcr", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "endpoint", "primary_blocker": "100k_router_still_blocked", "next_required_step": "keep endpoint"},
                {"family": "ion_channel", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "kinase", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "idp", "pretest_ready": "yes", "claim_safe_test_ready": "subset_only", "current_state": "subset", "primary_blocker": "broader_full_idp_promotion_blocked", "next_required_step": "keep subset"},
                {"family": "non_kinase_enzyme_ca2", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2"},
                {"family": "nuclear_receptor_pxr", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR"},
                {"family": "transporter", "pretest_ready": "no", "claim_safe_test_ready": "no", "current_state": "blocked", "primary_blocker": "local_evidence_and_donor_policy_blocked", "next_required_step": "finish manual review"},
            ]
        },
        {"rows": []},
        {
            "summary": {
                "transporter_placeholder_driven_rows": 9,
                "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013",
                "ca2_direct_conflict_row_count": 5,
                "pxr_must_defer_count": 3,
                "pxr_confirmation_primary_focus_ligand": "bexarotene",
            }
        },
        {
            "summary": {
                "queue_row_count": 8,
                "top_queue_id": "seed_core_binder_01",
                "next_required_step": "Start with AQP1 core_binder_01, carry AqB013 as the exact-human-activity provenance hold, then burn down placeholder-driven transporter rows.",
            }
        },
        aqp1_source_confirmation_payload={
            "summary": {
                "primary_focus_ligand": "bacopaside II",
                "exact_human_reference_ligand": "AqB013",
                "claim_safe_kcal_ready_count": 0,
            }
        },
        aqp1_follow_on_packet_payload={
            "summary": {
                "row_count": 2,
                "follow_on_targets": "core_binder_02, core_binder_03",
            }
        },
    )
    summary = payload["summary"]
    rows = {row["family"]: row for row in payload["rows"]}
    assert summary["aqp1_first_wave_follow_on_packet_artifact"] == "runs/aqp1_first_wave_follow_on_packet_current.md"
    assert summary["aqp1_first_wave_follow_on_targets"] == "core_binder_02, core_binder_03"
    assert summary["aqp1_first_wave_follow_on_lane_label"] == "core_binder_02/03"
    assert summary["aqp1_first_wave_follow_on_row_count"] == 2
    _contains_tokens(summary["aqp1_operator_provenance_note"], "AqB013 exact human AQP1 target-activity provenance, kcal blank")
    _contains_tokens(summary["next_required_step"], "core_binder_01", "core_binder_02/03", "aqb013 exact human", "follow-on")
    _contains_tokens(rows["transporter"]["closure_signal"], "follow_on_artifact=runs/aqp1_first_wave_follow_on_packet_current.md", "follow_on_targets=core_binder_02, core_binder_03", "follow_on_lane=core_binder_02/03")
    _contains_tokens(rows["transporter"]["next_burndown_action"], "core_binder_01", "aqb013 exact human", "core_binder_02/03")


def test_build_commercialization_gap_burndown_propagates_nightly_gate_burndown() -> None:
    payload = mod.build_payload(
        {
            "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
            "rows": [
                {"family": "gpcr", "score": 82, "primary_blocker": "router", "source_artifact": "gpcr.md"},
                {"family": "ion_channel", "score": 88, "primary_blocker": "", "source_artifact": "ion.md"},
                {"family": "kinase", "score": 90, "primary_blocker": "", "source_artifact": "kinase.md"},
                {"family": "idp", "score": 70, "primary_blocker": "broader_full_idp_promotion_blocked", "source_artifact": "idp.md"},
                {"family": "non_kinase_enzyme_ca2", "score": 58, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "ca2.md"},
                {"family": "nuclear_receptor_pxr", "score": 62, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "pxr.md"},
                {"family": "transporter", "score": 32, "primary_blocker": "local_evidence_and_donor_policy_blocked", "source_artifact": "tx.md"},
            ],
        },
        {
            "rows": [
                {"family": "gpcr", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "endpoint", "primary_blocker": "100k_router_still_blocked", "next_required_step": "keep endpoint"},
                {"family": "ion_channel", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "kinase", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "idp", "pretest_ready": "yes", "claim_safe_test_ready": "subset_only", "current_state": "subset", "primary_blocker": "broader_full_idp_promotion_blocked", "next_required_step": "keep subset"},
                {"family": "non_kinase_enzyme_ca2", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2"},
                {"family": "nuclear_receptor_pxr", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR"},
                {"family": "transporter", "pretest_ready": "no", "claim_safe_test_ready": "no", "current_state": "blocked", "primary_blocker": "local_evidence_and_donor_policy_blocked", "next_required_step": "finish manual review"},
            ]
        },
        {"rows": []},
        {"summary": {"transporter_placeholder_driven_rows": 9, "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013", "ca2_direct_conflict_row_count": 5, "pxr_must_defer_count": 3, "pxr_confirmation_primary_focus_ligand": "bexarotene"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "next_required_step": "Start with AQP1 core_binder_01, carry AqB013 as the exact-human-activity provenance hold, then burn down placeholder-driven transporter rows."}},
        aqp1_source_confirmation_payload={"summary": {"primary_focus_ligand": "bacopaside II", "exact_human_reference_ligand": "AqB013", "claim_safe_kcal_ready_count": 0}},
        aqp1_follow_on_packet_payload={"summary": {"row_count": 2, "follow_on_targets": "core_binder_02, core_binder_03"}},
        local_engine_commercialization_queue_payload=LOCAL_ENGINE_STAGE6_GATE_QUEUE,
    )

    summary = payload["summary"]
    transporter_row = next(row for row in payload["rows"] if row["family"] == "transporter")
    assert summary["local_engine_commercialization_queue_nightly_gate_burndown_artifact"] == (
        "runs/nightly_gate_burndown_packet_current.md"
    )
    assert summary["local_engine_commercialization_queue_nightly_gate_primary_metric"] == "mean_min_distance_A"
    _contains_tokens(
        summary["next_required_step"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )
    _contains_tokens(
        transporter_row["next_burndown_action"],
        "nightly_gate_burndown_packet_current.md",
        "mean_min_distance_a",
    )


def test_build_commercialization_gap_burndown_zeroes_active_blocked_count_when_tracked_closed(tmp_path) -> None:
    payload = mod.build_payload(
        {
            "summary": {"core_commercial_lane_score": 82.5, "all_category_expansion_score": 68.9},
            "rows": [
                {"family": "gpcr", "score": 82, "primary_blocker": "router", "source_artifact": "gpcr.md"},
                {"family": "ion_channel", "score": 88, "primary_blocker": "", "source_artifact": "ion.md"},
                {"family": "kinase", "score": 90, "primary_blocker": "", "source_artifact": "kinase.md"},
                {"family": "idp", "score": 70, "primary_blocker": "broader_full_idp_promotion_blocked", "source_artifact": "idp.md"},
                {"family": "non_kinase_enzyme_ca2", "score": 58, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "ca2.md"},
                {"family": "nuclear_receptor_pxr", "score": 62, "primary_blocker": "replacement_reference_binding_kcal_mol", "source_artifact": "pxr.md"},
                {"family": "transporter", "score": 32, "primary_blocker": "local_evidence_and_donor_policy_blocked", "source_artifact": "tx.md"},
            ],
        },
        {
            "rows": [
                {"family": "gpcr", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "endpoint", "primary_blocker": "100k_router_still_blocked", "next_required_step": "keep endpoint"},
                {"family": "ion_channel", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "kinase", "pretest_ready": "yes", "claim_safe_test_ready": "yes", "current_state": "measured", "primary_blocker": "", "next_required_step": "keep stable"},
                {"family": "idp", "pretest_ready": "no", "claim_safe_test_ready": "no", "current_state": "parked", "primary_blocker": "broader_full_idp_promotion_blocked", "next_required_step": "keep broader IDP parked"},
                {"family": "non_kinase_enzyme_ca2", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill CA2"},
                {"family": "nuclear_receptor_pxr", "pretest_ready": "partial", "claim_safe_test_ready": "no", "current_state": "partial", "primary_blocker": "replacement_reference_binding_kcal_mol", "next_required_step": "fill PXR"},
                {"family": "transporter", "pretest_ready": "no", "claim_safe_test_ready": "no", "current_state": "blocked", "primary_blocker": "local_evidence_and_donor_policy_blocked", "next_required_step": "finish manual review"},
            ]
        },
        {"rows": []},
        {"summary": {"transporter_placeholder_driven_rows": 6, "aqp1_quantitative_provenance_primary_focus_ligand": "AqB013"}},
        {"summary": {"queue_row_count": 8, "top_queue_id": "seed_core_binder_01", "blocked_count": 2}},
        transporter_placeholder_burndown_queue_payload=TRANSPORTER_PLACEHOLDER_ACCOUNTING_CLOSED,
        aqp1_functional_kcal_surrogate_payload=AQP1_FUNCTIONAL_SURROGATE_ACCOUNTING_CLOSED,
        local_engine_commercialization_queue_payload=LOCAL_ENGINE_CLEAR_QUEUE,
    )

    summary = payload["summary"]
    assert summary["tracked_gap_accounting_closed"] is True
    assert summary["highest_gap_family"] == "none_tracked_commercialization_gap"
    assert summary["blocked_count"] == 0
    assert summary["raw_blocked_bucket_count"] == 2
    assert summary["parked_or_review_only_blocked_count"] == 2
    assert summary["transporter_placeholder_driven_rows"] == 0
    assert summary["transporter_placeholder_driven_rows_legacy_execution"] == 6
    rows = {row["family"]: row for row in payload["rows"]}
    assert rows["transporter"]["burndown_bucket"] == "blocked"
    assert rows["idp"]["burndown_bucket"] == "blocked"
    _contains_tokens(
        summary["next_required_step"],
        "all tracked commercialization gap accounting blockers are closed",
        "wetlab readiness evidence attached",
    )
    out_md = tmp_path / "commercialization_gap_burndown_current.md"
    mod._write_markdown(out_md, payload)
    markdown = out_md.read_text(encoding="utf-8")
    _contains_tokens(
        markdown,
        "blocked_count: `0`",
        "raw_blocked_bucket_count: `2`",
        "parked_or_review_only_blocked_count: `2`",
    )
