from __future__ import annotations

import inspect
import json
import os
import sys

from tools.wetlab_target_render_utils import load_json
from tools import build_runs_cleanup_batch2_manifest as cleanup_manifest_mod
from tools import build_wetlab_partner_first_contact_export_bundle as export_mod
from tools import build_wetlab_antiviral_first_contact_packets as antiviral_fc_mod
from tools import build_wetlab_antiviral_wave1_rail as antiviral_rail_mod
from tools import build_ca_ix_one_page_brief as caix_brief_mod
from tools import build_wetlab_mpro_vendor_cost_check as vendor_mod
from tools import build_wetlab_outbound_execution_priority_board as outbound_priority_mod
from tools import build_wetlab_neglected_first_contact_packets as neglected_fc_mod
from tools import build_wetlab_neglected_outreach_packet as neglected_outreach_mod
from tools import build_wetlab_neglected_wave1_rows as neglected_rows_mod
from tools import build_wetlab_oncology_first_contact_packet as oncology_fc_mod
from tools import build_wetlab_partner_outreach_tracks as outreach_mod
from tools import build_wetlab_partner_export_schema as export_schema_mod
from tools import build_wetlab_partner_target_portfolio as portfolio_mod
from tools import build_wetlab_partnering_stack as mod
from tools import build_wetlab_priority3_target_render_split as render_split_mod
from tools import build_wetlab_next3_novelty_fill_map as next_novelty_mod
from tools import build_wetlab_next3_repurposing_fill_map as next_fill_mod
from tools import build_wetlab_priority3_novelty_fill_map as novelty_fill_mod
from tools import build_wetlab_priority3_repurposing_fill_map as fill_map_mod
from tools import build_wetlab_priority3_repurposing_seed_pool as seed_mod
from tools import build_wetlab_domain_generation_schema as domain_schema_mod
from tools import build_wetlab_broad_screen_library_spec as broad_library_mod
from tools import build_wetlab_broad_screen_queue as broad_queue_mod
from tools import build_wetlab_broad_screen_bridge as broad_bridge_mod
from tools import build_wetlab_broad_screen_compound_universe as broad_universe_mod
from tools import build_wetlab_broad_screen_bulk_results as broad_bulk_results_mod
from tools import build_wetlab_broad_screen_repurposing_autofill as broad_autofill_mod
from tools import build_wetlab_broad_screen_execution_queue as broad_execution_mod
from tools.wetlab import build_wetlab_broad_screen_runtime_runbook as broad_runbook_mod
from tools import build_wetlab_validation_companion_panels as companion_mod
from tools import build_wetlab_wave1_brief_fill_queue as fill_queue_mod
from tools import build_wetlab_one_page_brief_schema as schema_mod
from tools import build_wetlab_wave1_campaign_blueprint as blueprint_mod
from tools import build_wetlab_wave1_rail_packet_index as rail_index_mod
from tools import build_wetlab_wave1_one_page_briefs as one_page_mod
from tools import build_wetlab_wave1_target_brief_matrix as brief_matrix_mod
from tools import build_wetlab_wave1_target_brief_packets as brief_index_mod
from tools import build_wetlab_first_contact_brief_bundle as first_contact_mod
from tools import build_wetlab_wave1_packet_queue as queue_mod
from tools import build_wetlab_wave1_kinase_first_contact_packets as kinase_fc_mod
from tools import build_wetlab_wave1_kinase_rail_packets as kinase_rail_mod
from tools import build_wetlab_kinase_outreach_packet as kinase_outreach_mod
from tools import build_wetlab_stk17b_novelty_fill_map as stk17b_novelty_mod
from tools import build_wetlab_stk17b_repurposing_fill_map as stk17b_fill_mod
from tools import build_sarscov2_mpro_render_suite as mpro_render_mod
from tools import build_caix_render_suite as caix_render_mod
from tools import build_tcruzi_pde_render_suite as tcruzi_render_mod
from tools import build_wetlab_prep_artifact_lane as prep_lane_mod
from tools import build_wetlab_priority3_protein_run_queue as run_queue_mod
from tools import build_sarscov2_mpro_launch_packet as mpro_launch_mod
from tools import build_sarscov2_mpro_run_record as mpro_record_mod
from tools import build_caix_launch_packet as caix_launch_mod
from tools import build_caix_run_record as caix_record_mod
from tools import build_tcruzi_pde_launch_packet as tcruzi_launch_mod
from tools import build_sarscov2_mpro_run_status as mpro_status_mod
from tools import build_caix_result_review as caix_review_mod
from tools import build_tcruzi_pde_run_record as tcruzi_record_mod
from tools import build_tcruzi_pde_result_review as tcruzi_review_mod
from tools import build_wetlab_priority3_runtime_event as runtime_event_mod
from tools import build_wetlab_priority3_runtime_runbook as runtime_runbook_mod
from tools import build_wetlab_stk17b_exploratory_retry_lane as stk17b_exploratory_mod


def test_build_wetlab_partnering_stack(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    portfolio = portfolio_mod.build_payload()
    blueprint = blueprint_mod.build_payload(portfolio)
    brief_matrix = brief_matrix_mod.build_payload()
    companion = companion_mod.build_payload(portfolio)
    outreach = outreach_mod.build_payload()
    schema = schema_mod.build_payload()
    queue = queue_mod.build_payload(portfolio, blueprint, companion, outreach)
    one_page = one_page_mod.build_payload(portfolio, blueprint, outreach)
    initial_fill_queue = fill_queue_mod.build_payload(queue, schema)
    fill_map = fill_map_mod.build_payload(seed_mod.build_payload(), initial_fill_queue, queue)
    novelty_fill = novelty_fill_mod.build_payload(fill_map)
    next_fill = next_fill_mod.build_payload(initial_fill_queue, queue)
    next_novelty = next_novelty_mod.build_payload(next_fill)
    stk17b_fill = stk17b_fill_mod.build_payload(initial_fill_queue, queue)
    stk17b_novelty = stk17b_novelty_mod.build_payload(stk17b_fill)
    vendor_cost = vendor_mod.build_payload(fill_map)
    brief_index = brief_index_mod.build_payload(portfolio, blueprint, companion, outreach, schema, fill_map, novelty_fill, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    fill_queue = fill_queue_mod.build_payload(queue, schema, fill_map, novelty_fill, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    first_contact = first_contact_mod.build_payload(fill_map, novelty_fill, vendor_cost)
    domain_schema = domain_schema_mod.build_payload()
    export_schema = export_schema_mod.build_payload()
    render_split = render_split_mod.build_payload()

    neglected_rows = neglected_rows_mod.build_payload()
    neglected_first_contact = neglected_fc_mod.build_payload(first_contact, next_fill, next_novelty)
    neglected_json = tmp_path / "wetlab_neglected_first_contact_packets_current.json"
    neglected_json.write_text(json.dumps(neglected_first_contact, ensure_ascii=False), encoding="utf-8")
    neglected_outreach = neglected_outreach_mod.build_payload(str(neglected_json))
    antiviral_rail = antiviral_rail_mod.build_payload(portfolio, blueprint, companion, outreach)
    antiviral_first_contact = antiviral_fc_mod.build_payload(antiviral_rail, first_contact, outreach, fill_map, novelty_fill, next_fill, next_novelty, vendor_cost)
    kinase_rail = kinase_rail_mod.build_payload(portfolio, blueprint, companion, outreach)
    kinase_first_contact = kinase_fc_mod.build_payload(kinase_rail, first_contact, schema, outreach, next_fill, next_novelty, stk17b_fill, stk17b_novelty)
    kinase_outreach = kinase_outreach_mod.build_payload(kinase_first_contact, outreach)
    caix_brief = caix_brief_mod.build_payload(portfolio, blueprint, companion, outreach)
    oncology_first_contact = oncology_fc_mod.build_payload(caix_brief, first_contact, outreach, companion, fill_map, novelty_fill)
    export_bundle = export_mod.build_payload(neglected_outreach, oncology_first_contact, antiviral_first_contact, kinase_outreach)
    mpro_render = mpro_render_mod.build_payload(brief_index, antiviral_rail, antiviral_first_contact, export_bundle, vendor_cost)
    caix_render = caix_render_mod.build_payload(brief_index, caix_brief, oncology_first_contact, export_bundle)
    tcruzi_render = tcruzi_render_mod.build_payload(brief_index, neglected_first_contact, export_bundle)
    mpro_launch = mpro_launch_mod.build_payload(
        mpro_render,
        mpro_render["artifacts"]["partner_export"],
        vendor_cost,
    )
    caix_launch = caix_launch_mod.build_payload(
        brief_index,
        caix_render,
        caix_render["artifacts"]["partner_export"],
        caix_render["artifacts"]["condition_card"],
    )
    tcruzi_launch = tcruzi_launch_mod.build_payload(
        brief_index,
        tcruzi_render,
        tcruzi_render["artifacts"]["partner_export"],
        tcruzi_render["artifacts"]["condition_card"],
    )
    prep_lane = prep_lane_mod.build_payload(mpro_render, caix_render, tcruzi_render)
    mpro_run_record = mpro_record_mod.build_payload(mpro_launch, {}, {})
    mpro_run_status = mpro_status_mod.build_payload(mpro_launch, mpro_run_record)
    caix_run_record = caix_record_mod.build_payload(caix_launch, {}, {})
    caix_result_review = caix_review_mod.build_payload(mpro_run_status, caix_launch, tcruzi_launch, caix_run_record)
    tcruzi_run_record = tcruzi_record_mod.build_payload(
        tcruzi_launch,
        caix_result_review,
        load_json(tcruzi_record_mod.DEFAULT_GO_NO_GO_JSON),
    )
    tcruzi_result_review = tcruzi_review_mod.build_payload(caix_result_review, tcruzi_launch, tcruzi_run_record)
    runtime_event = runtime_event_mod.build_payload(
        {
            "target_id": "SARS-CoV-2 Mpro",
            "event": "reset",
            "progress_command": "tools/build_sarscov2_mpro_live_progress.py --status not_started",
            "result_command": "tools/build_sarscov2_mpro_result_summary.py --status not_ready",
            "run_record_status": "sarscov2_mpro_run_record_ready",
            "execution_state": "ready_to_launch",
            "queue_status_now": "ready_first",
            "gate_status": "sarscov2_mpro_run_status_ready",
            "gate_execution_state": "ready_to_launch",
        }
    )
    runtime_runbook = runtime_runbook_mod.build_payload(run_queue_mod.build_payload(
        mpro_launch,
        caix_launch,
        tcruzi_launch,
        prep_lane,
        mpro_run_status,
        caix_result_review,
        tcruzi_result_review,
    ), {"summary": {
        "status": "wetlab_priority3_gate_refresh_ready",
        "mpro_execution_state": "ready_to_launch",
        "caix_review_state": "blocked_on_mpro_result_review",
        "tcruzi_execution_state": "blocked_on_previous_review",
    }})
    run_queue = run_queue_mod.build_payload(
        mpro_launch,
        caix_launch,
        tcruzi_launch,
        prep_lane,
        mpro_run_status,
        caix_result_review,
        tcruzi_result_review,
    )
    rail_index = rail_index_mod.build_payload(
        neglected_rows,
        neglected_first_contact,
        kinase_rail,
        kinase_first_contact,
        antiviral_rail,
        antiviral_first_contact,
        oncology_first_contact,
        fill_map,
        novelty_fill,
        next_fill,
        next_novelty,
        stk17b_fill,
        stk17b_novelty,
        vendor_cost,
    )
    next3_run_queue = load_json("runs/wetlab_next3_protein_run_queue_current.json")
    next3_chain_stack = load_json("runs/wetlab_next3_chain_stack_current.json")
    next3_runtime_event = load_json("runs/wetlab_next3_runtime_event_current.json")
    next3_runtime_runbook = load_json("runs/wetlab_next3_runtime_runbook_current.json")
    next3_execution_console = load_json("runs/wetlab_next3_execution_console_current.json")
    final2_run_queue = load_json("runs/wetlab_final2_protein_run_queue_current.json")
    final2_chain_stack = load_json("runs/wetlab_final2_chain_stack_current.json")
    final2_runtime_event = load_json("runs/wetlab_final2_runtime_event_current.json")
    final2_runtime_runbook = load_json("runs/wetlab_final2_runtime_runbook_current.json")
    final2_execution_console = load_json("runs/wetlab_final2_execution_console_current.json")
    wave2_run_queue = load_json("runs/wetlab_wave2_protein_run_queue_current.json")
    wave2_chain_stack = load_json("runs/wetlab_wave2_chain_stack_current.json")
    wave2_runtime_event = load_json("runs/wetlab_wave2_runtime_event_current.json")
    wave2_runtime_runbook = load_json("runs/wetlab_wave2_runtime_runbook_current.json")
    wave2_execution_console = load_json("runs/wetlab_wave2_execution_console_current.json")
    broad_antitarget_queue = load_json("runs/wetlab_broad_screen_antitarget_queue_current.json")
    broad_antitarget_execution_queue = load_json("runs/wetlab_broad_screen_antitarget_execution_queue_current.json")
    master_queue = {
        "summary": {
            "status": "wetlab_master_execution_queue_ready",
            "chain_count": 4,
            "resolved_target_count": 13,
            "stack_gate_states": {
                "priority3": {"all_rows_resolved": True},
                "next3": {"all_rows_resolved": True},
                "final2": {"all_rows_resolved": True},
                "wave2": {"all_rows_resolved": True},
            },
        }
    }
    master_runtime_runbook = {"summary": {"status": "wetlab_master_runtime_runbook_ready"}}
    master_execution_console = {"summary": {"status": "wetlab_master_execution_console_ready"}}
    master_terminal_review = {
        "summary": {
            "status": "wetlab_master_terminal_review_ready",
            "campaign_terminal_state": "complete",
            "ready_to_send_track_count": 5,
        }
    }
    outbound_priority_board = outbound_priority_mod.build_payload(export_bundle, portfolio, master_queue)
    final_campaign_summary = {
        "summary": {
            "status": "wetlab_final_campaign_summary_ready",
            "top_outbound_targets": "DNDi_IPK -> READDI_Korea -> M4K_open_science",
        }
    }
    broad_library = broad_library_mod.build_payload()
    broad_queue = broad_queue_mod.build_payload(portfolio, broad_library)
    broad_bridge = broad_bridge_mod.build_payload(broad_library, broad_queue)
    broad_universe = broad_universe_mod.build_payload()
    broad_bulk_results = broad_bulk_results_mod.build_payload()
    broad_autofill = broad_autofill_mod.build_payload(portfolio, broad_bridge, broad_bulk_results)
    broad_execution = broad_execution_mod.build_payload(broad_queue, broad_universe)
    broad_runbook = broad_runbook_mod.build_payload(broad_execution)
    broad_execution_summary = broad_execution["summary"]
    broad_antitarget_execution_summary = broad_antitarget_execution_queue["summary"]
    broad_primary_watch_state = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watcher_ready",
            "next_required_step": "Complete CA IX 08_of_20 automatically and consider auto-starting the next primary shard.",
            "compute_state": "summary_complete",
        }
    }
    broad_primary_watch = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watcher_ready",
            "next_required_step": "Pause auto-advance for STK17B (DRAK2); it hit 3 consecutive auto-holds. Review the target-level gate-failure surface before continuing.",
            "actions_taken_count": 1,
            "action_taken": "guard_stop_target_after_holds",
            "guard_blocked_target_id": "STK17B (DRAK2)",
            "guard_hold_streak": 3,
            "guard_hold_limit": 3,
        }
    }
    stk17b_exploratory_lane = stk17b_exploratory_mod.build_payload(
        {
            "summary": {
                "status": "wetlab_stk17b_manual_retry_lane_ready",
                "target_id": "STK17B (DRAK2)",
                "shard_id": "17_of_20",
                "campaign_start_shard_id": "13_of_20",
                "guard_active": True,
                "guard_limit": 3,
                "guard_hold_streak": 3,
                "ready_for_manual_retry": True,
                "selected_command_kind": "throughput_preflight_tuned_gate55",
                "throughput_execute_ready": True,
            }
        },
        {
            "summary": {
                "status": "wetlab_broad_screen_throughput_bridge_ready",
                "throughput_execute_ready": True,
            },
            "rows": [
                {
                    "command_kind": "throughput_preflight_tuned_gate45",
                    "command": "python3 tools/run_ligand_htvs_pipeline.py --gate-max-mean-min-distance-A 4.5",
                }
            ],
        },
        {
            "summary": {
                "recommended_relaxed_threshold_A": 4.5,
                "exploratory_median_threshold_A": 4.4,
            }
        },
    )
    retry_handoff_summary = {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "manual_retry_decision_count": 5,
            "manual_retry_focus_target_id": "STK17B (DRAK2)",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch",
            "selected_rescue_branch_next_required_step": "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision.",
            "selected_allatom_target_id": "Cathepsin K",
            "selected_allatom_surface_label": "cathepsin_k_allatom_review_packet",
            "selected_allatom_selected_command_kind": "allatom_refinement",
            "selected_allatom_selected_threshold_A": 2.5,
            "selected_allatom_packet_scope": "selected_allatom_review_packet",
            "selected_allatom_packet_ready_for_operator_review": True,
            "selected_allatom_wetlab_gate_pass": False,
            "selected_allatom_wetlab_final_gate_pass": False,
            "selected_allatom_claim_gate_available": True,
            "selected_allatom_claim_ready_for_allatom": False,
            "selected_allatom_commercial_schema_version": "wetlab_commercial_grade_v1",
            "selected_allatom_commercial_reported": True,
            "selected_allatom_commercial_hard_gate_reported": True,
            "selected_allatom_commercial_hard_gate_pass_v1": False,
            "selected_allatom_commercial_overall_score_v1": 44.6,
            "selected_allatom_commercial_risk_bucket_v1": "critical",
            "selected_allatom_commercial_decision_class_v1": "commercial_recycle_or_rework",
            "selected_allatom_commercial_primary_upgrade_actions_v1": [
                "tighten_pose_geometry_under_strict_gate",
                "raise_trajectory_stability",
                "increase_trajectory_support",
            ],
            "selected_allatom_best_compound_name": "Cathepsin Lead",
            "selected_allatom_best_compound_name_human_readable": "Cathepsin Lead",
            "selected_allatom_best_compound_name_resolution": "human_readable",
            "selected_allatom_best_mean_min_distance_A": 1.234,
            "selected_allatom_promoted_candidate_count": 4,
            "selected_allatom_under_2p5_candidate_count": 1,
            "selected_allatom_near_candidate_count": 3,
            "selected_allatom_next_required_step": "Review Cathepsin K selected all-atom packet before any wetlab decision.",
        }
    }
    broad_screen_dpre1_branch_review_surface = {
        "summary": {
            "status": "wetlab_dpre1_branch_review_surface_ready",
            "target_id": "DprE1",
            "branch_label": "dpre1_guarded_review_branch",
            "exploratory_retry_next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
            "next_required_step": "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }
    broad_screen_stk17b_exploratory_followup_lane = {
        "summary": {
            "status": "wetlab_stk17b_exploratory_followup_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "18_of_20",
            "ready_for_manual_retry": True,
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "followup_lane_label": "exploratory_gate4.5_followup",
            "followup_shard_ids": "18_of_20;19_of_20;20_of_20",
            "hard_freeze_state": "hard_freeze_after_exploratory_success",
            "freeze_note": "Auto-start remains hard-frozen after the gate4.5 success; shards 18-20 are routed to the exploratory gate4.5 follow-up lane and should be reviewed separately before reopening.",
            "next_required_step": "Run the STK17B (DRAK2) exploratory gate4.5 follow-up runner for 18_of_20; keep auto-start hard-frozen after the gate4.5 success and review shards 18-20 separately before reopening.",
        }
    }
    broad_screen_stk17b_followup_review_surface = {
        "summary": {
            "status": "wetlab_stk17b_followup_review_surface_ready",
            "target_id": "STK17B (DRAK2)",
            "decision": "branch_to_gate45_only_keep_default_closed",
            "decision_rationale": "17_of_20 succeeded under the 4.5A exploratory gate while follow-up shards 18-20 held under the default 2.5A gate.",
            "next_required_step": "Keep the STK17B (DRAK2) default lane closed and branch this target into the gate4.5 exploratory lane only; treat 18_of_20;19_of_20;20_of_20 as default-gate follow-up holds, not as evidence against the 4.5A path, until the follow-up runner preserves the 4.5A threshold end-to-end.",
        }
    }
    broad_screen_lbdhodh_gate51_validation_review_surface = {
        "summary": {
            "status": "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "target_id": "Leishmania braziliensis DHODH",
            "promotion_label": "gate5.1_validated",
            "gate51_validated": True,
            "default_lane_reopen_allowed": False,
            "branch_to_gate51_only": True,
            "decision": "branch_to_gate51_only_keep_default_closed",
            "decision_rationale": "Default-lane shards 01_of_20-08_of_20 held, while gate5.1 validation shards starting at 09_of_20 all reached result_ready with HTVS_OK summaries, so DHODH should stay on the gate5.1 branch only.",
            "gate51_validation_row_count": 12,
            "gate51_validation_success_count": 12,
            "validated_command_kind": "throughput_preflight_tuned_gate51",
            "validated_threshold_A": 5.1,
            "next_required_step": "Promote Leishmania braziliensis DHODH as gate5.1 validated, keep the default lane closed, and use the gate5.1 family as the canonical retry path for future DHODH work.",
        }
    }
    broad_screen_stk17b_manual_retry_lane = {
        "summary": {
            "status": "wetlab_stk17b_manual_retry_lane_ready",
            "target_id": "STK17B (DRAK2)",
            "shard_id": "12_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the STK17B tuned gate55 manual retry runner for 12_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    broad_screen_plpro_manual_retry_lane = {
        "summary": {
            "status": "wetlab_plpro_manual_retry_lane_ready",
            "target_id": "SARS-CoV-2 PLpro",
            "shard_id": "17_of_20",
            "selected_command_kind": "throughput_preflight_tuned_gate55",
            "ready_for_manual_retry": True,
            "next_required_step": "Run the PLpro manual retry runner for 17_of_20; keep auto-start blocked until the guarded retry either lands a clean summary or is held again.",
        }
    }
    broad_screen_mapping_fix_retry_support = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_support_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    broad_screen_stage1_mapping_fix_lanes = {
        "summary": {
            "status": "wetlab_stage1_mapping_fix_lanes_ready",
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "next_required_step": "Run the stage1 mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until mapping clears.",
        }
    }
    broad_screen_mapping_fix_retry_policy_templates = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_policy_templates_ready",
            "template_target_count": 2,
            "ready_target_count": 2,
            "ready_targets": "SARS-CoV-2 Mpro; T. cruzi PDE",
            "focus_target_id": "SARS-CoV-2 Mpro",
            "focus_template_label": "mapping_fix_branch_only",
            "focus_selected_command_kind": "throughput_preflight",
            "next_required_step": "Run the mapping-fix retry runner for SARS-CoV-2 Mpro 01_of_20; keep auto-start blocked until the mapping diagnostics rerun lands a clean summary.",
        }
    }
    broad_screen_hard_target_rescue_lane = {
        "summary": {
            "status": "wetlab_hard_target_rescue_lane_ready",
            "target_id": "Cathepsin K",
            "shard_id": "05_of_20",
            "stage1_ok": True,
            "stage6_fail": True,
            "auto_hold_streak": 4,
            "selected_command_kind": "hard_target_rescue_lane",
            "lane_label": "hard_target_rescue_lane",
            "next_required_step": "Run the hard-target rescue lane for Cathepsin K 05_of_20; keep the default lane closed.",
        }
    }
    broad_screen_rescue_anchor_artifacts = {
        "summary": {
            "status": "wetlab_rescue_anchor_artifacts_ready",
            "target_id": "Cathepsin K",
            "anchor_artifact_count": 2,
            "rescue_only": True,
            "native_anchor_artifact": "cathepsin_native_anchor.csv",
            "pocket_anchor_artifact": "cathepsin_pocket_anchor.csv",
            "next_required_step": "Review rescue anchors for Cathepsin K; keep the default lane closed.",
        }
    }
    broad_screen_rescue_three_bead_candidates = {
        "summary": {
            "status": "wetlab_rescue_three_bead_candidates_ready",
            "target_id": "T. cruzi PDE",
            "candidate_count": 3,
            "top_n": 3,
            "selected_command_kind": "throughput_preflight_tuned_gate51",
            "selected_threshold_A": 5.1,
            "next_required_step": "Review 3-bead rescue candidates for T. cruzi PDE; keep the default lane closed.",
        }
    }
    broad_screen_kinase_retry_policy_templates = {
        "summary": {
            "status": "wetlab_kinase_retry_policy_templates_ready",
            "template_target_count": 3,
            "empirical_validated_target_count": 1,
            "gate45_only_target_count": 1,
            "guarded_gate55_candidate_target_count": 1,
            "focus_target_id": "STK17B (DRAK2)",
            "focus_template_label": "gate45_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate45",
            "next_required_step": "Keep STK17B on the gate4.5 branch-only kinase template, keep ALK2 on the guarded gate55 template, and treat LRRK2 as panel-first until broad failure evidence appears.",
        }
    }
    broad_screen_target_retry_policy_templates = {
        "summary": {
            "status": "wetlab_target_retry_policy_templates_ready",
            "template_target_count": 6,
            "empirical_validated_target_count": 2,
            "non_kinase_template_target_count": 3,
            "non_kinase_empirical_validated_target_count": 1,
            "guarded_gate55_candidate_target_count": 1,
            "guarded_gate51_candidate_target_count": 1,
            "focus_target_id": "Leishmania braziliensis DHODH",
            "focus_template_label": "gate51_branch_only_empirical",
            "focus_selected_command_kind": "throughput_preflight_tuned_gate51",
            "focus_selected_threshold_A": 5.1,
            "next_required_step": "Promote DHODH gate5.1 as validated, keep the default lane closed, and reserve any future DHODH reopen for an explicit new review.",
        }
    }
    broad_antitarget_watch_state = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_watcher_state_ready",
            "next_required_step": "Hold CA IX -> CA II 04_of_20 if the heartbeat loop is gone.",
        }
    }
    broad_antitarget_watch = {
        "summary": {
            "status": "wetlab_broad_screen_antitarget_watcher_ready",
            "next_required_step": "Run the anti-target watcher again or leave it in loop mode to keep compute-attached counterscreen state aligned with active compute state.",
        }
    }
    (tmp_path / "runs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "runs/wetlab_broad_screen_primary_watch_loop.pid").write_text(str(os.getpid()), encoding="utf-8")
    (tmp_path / "runs/wetlab_broad_screen_antitarget_watcher_loop.pid").write_text(str(os.getpid()), encoding="utf-8")
    cleanup_manifest = cleanup_manifest_mod.build_payload("runs", "2026-03-29")

    payload = mod.build_payload(
        portfolio,
        blueprint,
        brief_matrix,
        companion,
        outreach,
        rail_index,
        schema,
        queue,
        one_page,
        brief_index,
        fill_queue,
        first_contact,
        fill_map,
        novelty_fill,
        next_fill,
        next_novelty,
        vendor_cost,
        export_bundle,
        cleanup_manifest,
        domain_generation_schema=domain_schema,
        partner_export_schema=export_schema,
        priority3_render_split=render_split,
        mpro_render_suite=mpro_render,
        caix_render_suite=caix_render,
        tcruzi_pde_render_suite=tcruzi_render,
        prep_artifact_lane=prep_lane,
        priority3_run_queue=run_queue,
        mpro_launch_packet=mpro_launch,
        caix_launch_packet=caix_launch,
        tcruzi_pde_launch_packet=tcruzi_launch,
        mpro_run_record=mpro_run_record,
        caix_run_record=caix_run_record,
        tcruzi_pde_run_record=tcruzi_run_record,
        mpro_run_status=mpro_run_status,
        caix_result_review=caix_result_review,
        tcruzi_pde_result_review=tcruzi_result_review,
        priority3_runtime_event=runtime_event,
        priority3_runtime_runbook=runtime_runbook,
        next3_run_queue=next3_run_queue,
        next3_chain_stack=next3_chain_stack,
        next3_runtime_event=next3_runtime_event,
        next3_runtime_runbook=next3_runtime_runbook,
        next3_execution_console=next3_execution_console,
        final2_run_queue=final2_run_queue,
        final2_chain_stack=final2_chain_stack,
        final2_runtime_event=final2_runtime_event,
        final2_runtime_runbook=final2_runtime_runbook,
        final2_execution_console=final2_execution_console,
        wave2_run_queue=wave2_run_queue,
        wave2_chain_stack=wave2_chain_stack,
        wave2_runtime_event=wave2_runtime_event,
        wave2_runtime_runbook=wave2_runtime_runbook,
        wave2_execution_console=wave2_execution_console,
        master_queue=master_queue,
        master_runtime_runbook=master_runtime_runbook,
        master_execution_console=master_execution_console,
        master_terminal_review=master_terminal_review,
        outbound_execution_priority_board=outbound_priority_board,
        final_campaign_summary=final_campaign_summary,
        broad_screen_library_spec=broad_library,
        broad_screen_queue=broad_queue,
        broad_screen_bridge=broad_bridge,
        broad_screen_compound_universe=broad_universe,
        broad_screen_bulk_results=broad_bulk_results,
        broad_screen_repurposing_autofill=broad_autofill,
        broad_screen_execution_queue=broad_execution,
        broad_screen_runtime_runbook=broad_runbook,
        broad_screen_antitarget_queue=broad_antitarget_queue,
        broad_screen_antitarget_execution_queue=broad_antitarget_execution_queue,
        broad_screen_primary_watch_state=broad_primary_watch_state,
        broad_screen_primary_watch=broad_primary_watch,
        broad_screen_antitarget_watch_state=broad_antitarget_watch_state,
        broad_screen_antitarget_watch=broad_antitarget_watch,
        broad_screen_current_results_index={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_best_mean_min_distance_A": 3.375,
                "selected_allatom_best_mean_min_distance_A_source": (
                    "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
                ),
            }
        },
        broad_screen_retry_handoff_summary=retry_handoff_summary,
        broad_screen_dpre1_branch_review_surface=broad_screen_dpre1_branch_review_surface,
        broad_screen_stk17b_manual_retry_lane=broad_screen_stk17b_manual_retry_lane,
        broad_screen_stk17b_exploratory_retry_lane=stk17b_exploratory_lane,
        broad_screen_stk17b_exploratory_followup_lane=broad_screen_stk17b_exploratory_followup_lane,
        broad_screen_stk17b_followup_review_surface=broad_screen_stk17b_followup_review_surface,
        broad_screen_lbdhodh_gate51_validation_review_surface=broad_screen_lbdhodh_gate51_validation_review_surface,
        broad_screen_plpro_manual_retry_lane=broad_screen_plpro_manual_retry_lane,
        broad_screen_mapping_fix_retry_support=broad_screen_mapping_fix_retry_support,
        broad_screen_stage1_mapping_fix_lanes=broad_screen_stage1_mapping_fix_lanes,
        broad_screen_mapping_fix_retry_policy_templates=broad_screen_mapping_fix_retry_policy_templates,
        broad_screen_hard_target_rescue_lane=broad_screen_hard_target_rescue_lane,
        broad_screen_rescue_anchor_artifacts=broad_screen_rescue_anchor_artifacts,
        broad_screen_rescue_three_bead_candidates=broad_screen_rescue_three_bead_candidates,
        broad_screen_kinase_retry_policy_templates=broad_screen_kinase_retry_policy_templates,
        broad_screen_target_retry_policy_templates=broad_screen_target_retry_policy_templates,
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_partnering_stack_ready"
    assert summary["artifact_kind"] == "wetlab_partnering_stack"
    assert summary["artifact_schema_version"] == "wetlab_partnering_stack.v1"
    assert summary["artifact_completeness"] == "full_partnering_stack"
    assert summary["portfolio_target_count"] == 14
    assert summary["wave1_target_count"] == 8
    assert summary["brief_matrix_count"] == 8
    assert summary["companion_panel_count"] == 13
    assert summary["outreach_track_count"] == 5
    assert summary["rail_packet_index_ready"] is True
    assert summary["brief_schema_ready"] is True
    assert summary["domain_generation_schema_ready"] is True
    assert summary["partner_export_schema_ready"] is True
    assert summary["priority3_render_split_ready"] is True
    assert summary["sarscov2_mpro_render_suite_ready"] is True
    assert summary["caix_render_suite_ready"] is True
    assert summary["tcruzi_pde_render_suite_ready"] is True
    assert summary["priority3_target_overlay_ready_count"] == 3
    assert summary["prep_artifact_lane_ready"] is True
    assert summary["priority3_run_queue_ready"] is True
    assert summary["mpro_launch_packet_ready"] is True
    assert summary["caix_launch_packet_ready"] is True
    assert summary["tcruzi_pde_launch_packet_ready"] is True
    assert summary["priority3_launch_packet_ready_count"] == 3
    assert summary["mpro_run_record_ready"] is True
    assert summary["caix_run_record_ready"] is True
    assert summary["tcruzi_pde_run_record_ready"] is True
    run_record_ready_count = sum(
        1
        for key in (
            "mpro_run_record_ready",
            "caix_run_record_ready",
            "tcruzi_pde_run_record_ready",
        )
        if summary.get(key) is True
    )
    assert summary["priority3_run_record_ready_count"] == run_record_ready_count
    assert summary["mpro_run_status_ready"] is True
    assert summary["caix_result_review_ready"] is True
    assert summary["tcruzi_pde_result_review_ready"] is True
    assert summary["priority3_runtime_event_ready"] is True
    assert summary["priority3_runtime_runbook_ready"] is True
    assert summary["priority3_transition_artifact_ready_count"] == 3
    assert summary["wave1_packet_queue_ready"] is True
    assert summary["one_page_brief_starters_ready"] is True
    assert summary["target_brief_index_ready"] is True
    assert summary["brief_fill_queue_ready"] is True
    assert summary["first_contact_bundle_ready"] is True
    assert summary["priority3_repurposing_fill_ready"] is True
    assert summary["priority3_novelty_fill_ready"] is True
    assert summary["next3_repurposing_fill_ready"] is True
    assert summary["next3_novelty_fill_ready"] is True
    assert summary["next3_run_queue_ready"] is True
    assert summary["next3_chain_stack_ready"] is True
    assert summary["next3_runtime_event_ready"] is True
    assert summary["next3_runtime_runbook_ready"] is True
    assert summary["next3_execution_console_ready"] is True
    assert summary["final2_run_queue_ready"] is True
    assert summary["final2_chain_stack_ready"] is True
    assert summary["final2_runtime_event_ready"] is True
    assert summary["final2_runtime_runbook_ready"] is True
    assert summary["final2_execution_console_ready"] is True
    assert summary["wave2_run_queue_ready"] is True
    assert summary["wave2_chain_stack_ready"] is True
    assert summary["wave2_runtime_event_ready"] is True
    assert summary["wave2_runtime_runbook_ready"] is True
    assert summary["wave2_execution_console_ready"] is True
    next3_summary = next3_run_queue["summary"]
    next3_chain_summary = next3_chain_stack["summary"]
    wave2_summary = wave2_run_queue["summary"]
    tcruzi_review_summary = tcruzi_result_review["summary"]
    assert summary["next3_ready_now_target_count"] == int(next3_summary["ready_now_target_count"])
    assert summary["next3_running_target_count"] == int(next3_summary["running_target_count"])
    assert summary["next3_resolved_target_count"] == int(next3_summary["resolved_target_count"])
    assert summary["wave2_ready_now_target_count"] == int(wave2_summary["ready_now_target_count"])
    assert summary["wave2_running_target_count"] == int(wave2_summary["running_target_count"])
    assert summary["wave2_resolved_target_count"] == int(wave2_summary["resolved_target_count"])
    assert summary["wave2_first_target"] == str(wave2_summary["first_target"])
    assert summary["wave2_queue_target_count"] == int(wave2_summary["queue_target_count"])
    assert summary["cruzain_next3_queue_status"] == str(next3_chain_summary["cruzain_queue_status"])
    assert summary["plpro_next3_queue_status"] == str(next3_chain_summary["sarscov2_plpro_queue_status"])
    assert summary["alk2_next3_queue_status"] == str(next3_chain_summary["alk2_queue_status"])
    assert summary["master_wave2_release_gate_status"] == str(tcruzi_review_summary["wave2_release_gate_status"])
    assert summary["master_wave2_release_blocked"] is bool(tcruzi_review_summary["wave2_release_blocked"])
    assert summary["master_wave2_ready"] is (not bool(tcruzi_review_summary["wave2_release_blocked"]))
    assert summary["master_wave2_queue_status"] == (
        "ready_after_previous_review" if not bool(tcruzi_review_summary["wave2_release_blocked"]) else "blocked_on_previous_review"
    )
    assert summary["mpro_vendor_cost_check_ready"] is True
    assert summary["first_contact_export_bundle_ready"] is True
    assert summary["cleanup_manifest_ready"] is True
    assert summary["master_terminal_review_ready"] is True
    assert summary["outbound_execution_priority_board_ready"] is True
    assert summary["final_campaign_summary_ready"] is True
    assert summary["broad_screen_library_spec_ready"] is True
    assert summary["broad_screen_queue_ready"] is True
    assert summary["broad_screen_bridge_ready"] is True
    assert summary["broad_screen_compound_universe_ready"] is True
    assert summary["broad_screen_bulk_results_ready"] is False
    assert summary["broad_screen_repurposing_autofill_ready"] is True
    assert summary["broad_screen_execution_queue_ready"] is True
    assert summary["broad_screen_runtime_runbook_ready"] is True
    assert summary["broad_screen_antitarget_queue_ready"] is True
    assert summary["broad_screen_antitarget_execution_queue_ready"] is True
    assert summary["broad_screen_primary_watch_state_ready"] is True
    assert summary["broad_screen_primary_watch_ready"] is True
    assert summary["broad_screen_primary_watch_next_required_step"] in {
        "Run the primary watcher again or leave it in loop mode to keep queue state aligned with compute state.",
        "Pause auto-advance for STK17B (DRAK2); it hit 3 consecutive auto-holds. Review the target-level gate-failure surface before continuing.",
    }
    assert summary["broad_screen_primary_watch_loop_attached"] is True
    assert summary["broad_screen_primary_watch_liveness"] == "attached"
    assert summary["broad_screen_primary_watch_fallback_mode"] == "compute-attached"
    assert summary["broad_screen_antitarget_watch_state_ready"] is True
    assert summary["broad_screen_antitarget_watch_ready"] is True
    assert summary["broad_screen_antitarget_watch_next_required_step"] == "Run the anti-target watcher again or leave it in loop mode to keep compute-attached counterscreen state aligned with active compute state."
    assert summary["broad_screen_antitarget_watch_loop_attached"] is True
    assert summary["broad_screen_antitarget_watch_liveness"] == "attached"
    assert summary["broad_screen_antitarget_watch_fallback_mode"] == "compute-attached"
    assert summary["broad_screen_retry_handoff_summary_ready"] is True
    assert summary["broad_screen_retry_handoff_manual_retry_decision_count"] == 5
    assert summary["broad_screen_retry_handoff_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["broad_screen_dpre1_branch_review_ready"] is True
    assert summary["broad_screen_dpre1_branch_review_next_required_step"] == "Keep the DprE1 default lane paused and refresh the stage6 tuning surface before retrying."
    assert summary["selected_rescue_branch_surface_label"] == "pde_rescue_only_branch"
    assert summary["selected_rescue_branch_next_required_step"] == "Operate T. cruzi PDE through the dedicated rescue-only branch, keep the default lane closed, and use the promoted top-4 packet as the review unit before any reopen decision."
    assert summary["selected_allatom_target_id"] == "Cathepsin K"
    assert summary["selected_allatom_surface_label"] == "cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_selected_command_kind"] == "allatom_refinement"
    assert summary["selected_allatom_selected_threshold_A"] == 2.5
    assert summary["selected_allatom_packet_scope"] == "selected_allatom_review_packet"
    assert summary["selected_allatom_focus_available"] is True
    assert summary["selected_allatom_focus_label"] == "Cathepsin K / cathepsin_k_allatom_review_packet"
    assert summary["selected_allatom_operator_review_ready_reported"] is True
    assert summary["selected_allatom_operator_review_ready"] is True
    assert summary["selected_allatom_wetlab_gate_reported"] is True
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_final_gate_reported"] is True
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["selected_allatom_final_wetlab_ready"] is False
    assert summary["selected_allatom_claim_gate_available_reported"] is True
    assert summary["selected_allatom_claim_gate_available"] is True
    assert summary["selected_allatom_claim_ready_for_allatom_reported"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is False
    assert summary["selected_allatom_readiness_semantics"] == "explicit_split_gate_fields"
    assert summary["selected_allatom_gate_rollup"] == "operator review ready | final gate blocked | claim gate available"
    assert summary["selected_allatom_gate_detail_rollup"] == (
        "wetlab gate blocked | semantics=explicit split-gate fields | "
        "best compound Cathepsin Lead | best mean min distance 1.234A | "
        "candidate bands promoted=4, strict<2.5A=1, near<3.0A=3"
    )
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["selected_allatom_human_summary"].startswith(
        "Selected all-atom focus Cathepsin K / cathepsin_k_allatom_review_packet: "
        "operator review ready, final gate blocked, claim gate available. "
        "wetlab gate blocked. Semantics: explicit split-gate fields. "
        "Details: best compound Cathepsin Lead; best mean min distance 1.234A; "
        "candidate bands promoted=4, strict<2.5A=1, near<3.0A=3."
    )
    assert "Commercial-grade v1: overall 44.6, risk critical, decision commercial_recycle_or_rework" in summary[
        "selected_allatom_human_summary"
    ]
    assert "Commercial-grade v2 is not yet reported for this focus." in summary[
        "selected_allatom_human_summary"
    ]
    assert "Translation-gate and stronger-physics shortlist signals are not yet reported for this focus." in summary[
        "selected_allatom_human_summary"
    ]
    assert summary["selected_allatom_best_compound_name"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_human_readable"] == "Cathepsin Lead"
    assert summary["selected_allatom_best_compound_name_resolution"] == "human_readable"
    assert summary["selected_allatom_best_mean_min_distance_A"] == 1.234
    assert summary["selected_allatom_best_mean_min_distance_A_source"] != (
        "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
    )
    assert summary["selected_allatom_promoted_candidate_count"] == 4
    assert summary["selected_allatom_under_2p5_candidate_count"] == 1
    assert summary["selected_allatom_near_candidate_count"] == 3
    assert summary["selected_allatom_next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
    assert summary["broad_screen_stk17b_exploratory_retry_lane_ready"] is True
    assert summary["broad_screen_stk17b_exploratory_retry_ready_for_manual_retry"] is True
    assert summary["broad_screen_stk17b_exploratory_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["broad_screen_stk17b_exploratory_retry_shard_id"] == "17_of_20"
    assert summary["broad_screen_stk17b_exploratory_retry_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["broad_screen_stk17b_exploratory_retry_selected_threshold_A"] == 4.5
    assert summary["broad_screen_stk17b_exploratory_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["broad_screen_stk17b_exploratory_freeze_target_id"] == "STK17B (DRAK2)"
    assert summary["broad_screen_stk17b_exploratory_freeze_hold_streak"] == 3
    assert summary["broad_screen_stk17b_exploratory_freeze_hold_limit"] == 3
    assert summary["broad_screen_stk17b_exploratory_followup_lane_ready"] is True
    assert summary["broad_screen_stk17b_exploratory_followup_target_id"] == "STK17B (DRAK2)"
    assert summary["broad_screen_stk17b_exploratory_followup_shard_id"] == "18_of_20"
    assert summary["broad_screen_stk17b_exploratory_followup_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["broad_screen_stk17b_exploratory_followup_lane_label"] == "exploratory_gate4.5_followup"
    assert summary["broad_screen_stk17b_exploratory_followup_freeze_state"] == "hard_freeze_after_exploratory_success"
    assert summary["broad_screen_stk17b_exploratory_followup_freeze_note"].startswith("Auto-start remains hard-frozen after the gate4.5 success")
    assert summary["broad_screen_stk17b_followup_review_surface_ready"] is True
    assert summary["broad_screen_stk17b_followup_review_decision"] == "branch_to_gate45_only_keep_default_closed"
    assert summary["broad_screen_stk17b_manual_retry_lane_ready"] is True
    assert summary["broad_screen_stk17b_manual_retry_ready_for_manual_retry"] is True
    assert summary["broad_screen_stk17b_manual_retry_target_id"] == "STK17B (DRAK2)"
    assert summary["broad_screen_stk17b_manual_retry_shard_id"] == "12_of_20"
    assert summary["broad_screen_stk17b_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["broad_screen_plpro_manual_retry_lane_ready"] is True
    assert summary["broad_screen_plpro_manual_retry_ready_for_manual_retry"] is True
    assert summary["broad_screen_plpro_manual_retry_target_id"] == "SARS-CoV-2 PLpro"
    assert summary["broad_screen_plpro_manual_retry_shard_id"] == "17_of_20"
    assert summary["broad_screen_plpro_manual_retry_selected_command_kind"] == "throughput_preflight_tuned_gate55"
    assert summary["broad_screen_mapping_fix_retry_support_ready"] is True
    assert summary["broad_screen_mapping_fix_retry_ready_target_count"] == 2
    assert summary["broad_screen_mapping_fix_retry_ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert summary["broad_screen_stage1_mapping_fix_lanes_ready"] is True
    assert summary["broad_screen_stage1_mapping_fix_ready_target_count"] == 2
    assert summary["broad_screen_stage1_mapping_fix_ready_targets"] == "SARS-CoV-2 Mpro; T. cruzi PDE"
    assert summary["broad_screen_mapping_fix_retry_policy_templates_ready"] is True
    assert summary["broad_screen_mapping_fix_retry_template_target_count"] == 2
    assert summary["broad_screen_mapping_fix_retry_ready_target_count"] == 2
    assert summary["broad_screen_mapping_fix_retry_focus_target_id"] == "SARS-CoV-2 Mpro"
    assert summary["broad_screen_mapping_fix_retry_focus_template_label"] == "mapping_fix_branch_only"
    assert summary["broad_screen_mapping_fix_retry_focus_selected_command_kind"] == "throughput_preflight"
    assert summary["broad_screen_mapping_fix_retry_next_required_step"].startswith("Run the mapping-fix retry runner for SARS-CoV-2 Mpro")
    assert summary["broad_screen_mapping_fix_retry_policy_templates_artifact"] == "runs/wetlab_mapping_fix_retry_policy_templates_current.md"
    assert summary["broad_screen_hard_target_rescue_lane_ready"] is True
    assert summary["broad_screen_hard_target_rescue_lane_target_id"] == "Cathepsin K"
    assert summary["broad_screen_hard_target_rescue_lane_shard_id"] == "05_of_20"
    assert summary["broad_screen_hard_target_rescue_lane_stage1_ok"] is True
    assert summary["broad_screen_hard_target_rescue_lane_stage6_fail"] is True
    assert summary["broad_screen_hard_target_rescue_lane_auto_hold_streak"] == 4
    assert summary["broad_screen_hard_target_rescue_lane_selected_command_kind"] == "hard_target_rescue_lane"
    assert summary["broad_screen_hard_target_rescue_lane_lane_label"] == "hard_target_rescue_lane"
    assert summary["broad_screen_hard_target_rescue_lane_next_required_step"].startswith("Run the hard-target rescue lane for Cathepsin K")
    assert summary["broad_screen_rescue_anchor_artifacts_ready"] is True
    assert summary["broad_screen_rescue_anchor_target_id"] == "Cathepsin K"
    assert summary["broad_screen_rescue_anchor_artifact_count"] == 2
    assert summary["broad_screen_rescue_anchor_rescue_only"] is True
    assert summary["broad_screen_rescue_anchor_native_anchor_artifact"] == "cathepsin_native_anchor.csv"
    assert summary["broad_screen_rescue_anchor_pocket_anchor_artifact"] == "cathepsin_pocket_anchor.csv"
    assert summary["broad_screen_rescue_anchor_next_required_step"].startswith("Review rescue anchors for Cathepsin K")
    assert summary["broad_screen_rescue_three_bead_candidates_ready"] is True
    assert summary["broad_screen_rescue_three_bead_candidate_target_id"] == "T. cruzi PDE"
    assert summary["broad_screen_rescue_three_bead_candidate_count"] == 3
    assert summary["broad_screen_rescue_three_bead_candidate_top_n"] == 3
    assert summary["broad_screen_rescue_three_bead_candidate_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_rescue_three_bead_candidate_selected_threshold_A"] == 5.1
    assert summary["broad_screen_rescue_three_bead_candidate_next_required_step"].startswith("Review 3-bead rescue candidates for T. cruzi PDE")
    assert summary["broad_screen_kinase_retry_policy_templates_ready"] is True
    assert summary["broad_screen_kinase_retry_template_target_count"] == 3
    assert summary["broad_screen_kinase_retry_empirical_validated_target_count"] == 1
    assert summary["broad_screen_kinase_retry_gate45_only_target_count"] == 1
    assert summary["broad_screen_kinase_retry_guarded_gate55_candidate_target_count"] == 1
    assert summary["broad_screen_kinase_retry_focus_target_id"] == "STK17B (DRAK2)"
    assert summary["broad_screen_kinase_retry_focus_template_label"] == "gate45_branch_only_empirical"
    assert summary["broad_screen_kinase_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate45"
    assert summary["broad_screen_target_retry_policy_templates_ready"] is True
    assert summary["broad_screen_target_retry_template_target_count"] == 6
    assert summary["broad_screen_target_retry_empirical_validated_target_count"] == 2
    assert summary["broad_screen_target_retry_non_kinase_template_target_count"] == 3
    assert summary["broad_screen_target_retry_non_kinase_empirical_validated_target_count"] == 1
    assert summary["broad_screen_target_retry_guarded_gate55_candidate_target_count"] == 1
    assert summary["broad_screen_target_retry_guarded_gate51_candidate_target_count"] == 1
    assert summary["broad_screen_target_retry_focus_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["broad_screen_target_retry_focus_template_label"] == "gate51_branch_only_empirical"
    assert summary["broad_screen_target_retry_focus_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_target_retry_focus_selected_threshold_A"] == 5.1
    assert summary["broad_screen_target_retry_next_required_step"].startswith("Promote DHODH gate5.1 as validated")
    assert summary["broad_screen_target_retry_policy_templates_artifact"] == "runs/wetlab_target_retry_policy_templates_current.md"
    assert summary["broad_screen_lbdhodh_gate51_validation_review_surface_ready"] is True
    assert summary["broad_screen_lbdhodh_gate51_validated"] is True
    assert summary["broad_screen_lbdhodh_gate51_validation_decision"] == "branch_to_gate51_only_keep_default_closed"
    assert summary["broad_screen_lbdhodh_gate51_validation_validated_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["broad_screen_lbdhodh_gate51_validation_validated_threshold_A"] == 5.1
    assert summary["selected_validated_target_id"] == "Leishmania braziliensis DHODH"
    assert summary["selected_validated_surface_label"] == "gate5.1_validation_review"
    assert summary["selected_validated_selected_command_kind"] == "throughput_preflight_tuned_gate51"
    assert summary["selected_validated_threshold_A"] == 5.1
    assert summary["selected_validated_next_required_step"].startswith("Promote Leishmania braziliensis DHODH as gate5.1 validated")
    assert summary["broad_screen_library_size"] == 100000
    assert summary["broad_screen_total_queue_rows"] == 260
    assert summary["broad_screen_ingested_compound_count"] >= 1
    assert summary["broad_screen_execution_ready_now_row_count"] == 1
    assert summary["broad_screen_antitarget_ready_now_row_count"] == 1
    assert summary["broad_screen_antitarget_running_row_count"] == int(broad_antitarget_execution_summary["running_row_count"])
    assert summary["broad_screen_antitarget_first_actionable_primary_target_id"] == str(
        broad_antitarget_execution_summary["first_actionable_primary_target_id"]
    )
    assert summary["broad_screen_antitarget_first_actionable_anti_target_id"] == str(
        broad_antitarget_execution_summary["first_actionable_anti_target_id"]
    )
    assert summary["broad_screen_first_actionable_target_id"] == str(broad_execution_summary["first_actionable_target_id"])
    assert summary["broad_screen_first_actionable_shard_id"] == str(broad_execution_summary["first_actionable_shard_id"])
    assert summary["campaign_terminal_state"] == "complete"
    assert summary["ready_to_send_track_count"] == 5
    assert summary["outbound_first_priority_target"] == "T. cruzi PDE; Cruzain"
    assert summary["outbound_follow_on_target_count"] == 4
    assert summary["final_campaign_top_outbound_targets"] == "DNDi_IPK -> READDI_Korea -> M4K_open_science"
    assert summary["next_required_step"] == "Review Cathepsin K selected all-atom packet before any wetlab decision."
    assert summary["open_eightyfirst"] == "runs/wetlab_kinase_retry_policy_templates_current.md"


def test_build_wetlab_partnering_stack_prefers_dengue_queue_source_priority(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    empty = {"summary": {}}
    dengue_execution_queue = {
        "summary": {
            "status": "wetlab_broad_screen_execution_queue_ready",
            "queue_row_count": 260,
            "resolved_row_count": 196,
            "running_row_count": 1,
            "first_actionable_target_id": "Dengue NS2B-NS3 protease",
            "first_actionable_shard_id": "17_of_20",
            "first_actionable_queue_status": "running",
            "next_required_step": "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner.",
        }
    }
    dengue_tuning_surface = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "recommended_observed_threshold_A": 4.5,
            "immediately_runnable_command_kind": "throughput_preflight_tuned_gate45",
        }
    }
    dengue_exploratory_retry_lane = {
        "summary": {
            "status": "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready",
            "target_id": "Dengue NS2B-NS3 protease",
            "shard_id": "14_of_20",
            "ready_for_manual_retry": False,
            "selected_command_kind": "throughput_preflight_tuned_gate45",
            "lane_label": "exploratory_gate4.5_followup",
            "next_required_step": "Keep the Dengue NS2B-NS3 protease default lane paused and refresh the stage6 tuning surface before retrying.",
        }
    }

    payload = mod.build_payload(
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        empty,
        broad_screen_execution_queue=dengue_execution_queue,
        broad_screen_dengue_stage6_tuning_surface=dengue_tuning_surface,
        broad_screen_dengue_exploratory_retry_lane=dengue_exploratory_retry_lane,
    )
    summary = payload["summary"]
    assert summary["broad_screen_dengue_stage6_retry_source_priority"] == "execution_queue"
    assert summary["broad_screen_dengue_stage6_retry_target_id"] == "Dengue NS2B-NS3 protease"
    assert summary["broad_screen_dengue_stage6_retry_shard_id"] == "17_of_20"
    assert summary["broad_screen_dengue_stage6_retry_next_required_step"] == "Continue or complete Dengue NS2B-NS3 protease shard 17_of_20 through the broad-screen runtime runner."
    assert summary["next_required_step"].startswith("Continue or complete Dengue NS2B-NS3 protease shard 17_of_20")


def test_build_wetlab_partnering_stack_selected_allatom_additive_surface_contract(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mod.selected_allatom_canonical_mod,
        "resolve_selected_allatom_canonical",
        lambda **kwargs: {
            "raw_claim_requirement_mode": "semi_hard",
            "raw_claim_requirement_provenance": "claim_gate_required_for_final_wetlab",
            "raw_claim_required_for_final_wetlab": True,
            "raw_claim_required_for_commercial_readiness": False,
            "raw_claim_requirement_reason": "claim/equivalence gate is required before final wetlab release.",
            "effective_actionability_status": "hard_blocked",
            "effective_actionability_claim_requirement_mode": "semi_hard",
            "effective_actionability_claim_requirement_status": "blocked",
            "effective_actionability_claim_requirement_reason": "claim/equivalence gate is semi-hard and blocked.",
            "effective_actionability_next_expensive_lane": "defer_expensive_lane",
            "effective_actionability_next_expensive_lane_reason": "translation gate is blocked before the expensive lane.",
            "effective_actionability_required_calculations": [
                "recompute_mean_min_distance_A",
                "resolve_claim_equivalence_gate",
            ],
            "effective_actionability_required_calculations_text": "recompute_mean_min_distance_A, resolve_claim_equivalence_gate",
            "effective_actionability_action_list": [
                {"severity": "hard", "action": "recompute_mean_min_distance_A", "status": "required"},
                {"severity": "semi_hard", "action": "resolve_claim_equivalence_gate", "status": "required"},
                {"severity": "soft", "action": "defer_expensive_lane", "status": "deferred", "lane": "defer_expensive_lane"},
            ],
            "effective_actionability_action_list_text": (
                "hard:recompute_mean_min_distance_A[required] | "
                "semi_hard:resolve_claim_equivalence_gate[required] | "
                "soft:defer_expensive_lane[deferred] lane=defer_expensive_lane"
            ),
            "effective_blocking_order": "hard_block_first",
            "effective_primary_blocking_domain": "translation_v2",
            "action_recipe_codes": [
                "recompute_mean_min_distance_A",
                "resolve_claim_equivalence_gate",
                "defer_expensive_lane",
            ],
            "action_recipe_rows": [
                {"severity": "hard", "action": "recompute_mean_min_distance_A", "status": "required"},
                {"severity": "semi_hard", "action": "resolve_claim_equivalence_gate", "status": "required"},
                {"severity": "soft", "action": "defer_expensive_lane", "status": "deferred", "lane": "defer_expensive_lane"},
            ],
            "action_recipe_rollup_text": (
                "recompute_mean_min_distance_A, resolve_claim_equivalence_gate, defer_expensive_lane | "
                "hard:recompute_mean_min_distance_A[required] | "
                "semi_hard:resolve_claim_equivalence_gate[required] | "
                "soft:defer_expensive_lane[deferred] lane=defer_expensive_lane"
            ),
            "translation_gate_version": "three_bead_to_allatom_translation_v1",
            "translation_gate_focus_status": "fail",
            "translation_gate_focus_score": 0.0,
            "translation_gate_focus_reason": "",
            "focus_shortlist_tier": "defer",
            "recommended_next_expensive_lane": "defer_expensive_lane",
            "recommended_next_expensive_lane_reason": "",
            "translation_provenance_mode": "inferred_from_partial_upstream",
                "commercial_provenance_mode_v2": "not_reported",
            "hybrid_policy": "canonical_scores_source_only__translation_shortlist_labeled_fallback",
            "human_summary": (
                "Raw claim requirement semi_hard; effective actionability hard_blocked; "
                "blocking order hard_block_first; "
                "action recipe recompute_mean_min_distance_A, resolve_claim_equivalence_gate, defer_expensive_lane."
            ),
        },
    )
    empty = {"summary": {}}
    payload = mod.build_payload(
        *([empty] * 19),
        broad_screen_retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_selected_command_kind": "allatom_refinement",
                "selected_allatom_selected_threshold_A": 2.5,
                "selected_allatom_packet_scope": "selected_allatom_review_packet",
                "selected_allatom_operator_review_ready_reported": True,
                "selected_allatom_operator_review_ready": True,
                "selected_allatom_wetlab_gate_reported": True,
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_reported": True,
                "selected_allatom_final_gate_pass": False,
                "selected_allatom_claim_gate_available_reported": True,
                "selected_allatom_claim_gate_available": False,
                "selected_allatom_claim_ready_for_allatom_reported": True,
                "selected_allatom_claim_ready_for_allatom": False,
                "selected_allatom_packet_ready_for_operator_review": True,
                "selected_allatom_wetlab_final_gate_pass": False,
                "selected_allatom_commercial_schema_version": "wetlab_commercial_grade_v1",
                "selected_allatom_commercial_reported": True,
                "selected_allatom_commercial_hard_gate_reported": True,
                "selected_allatom_commercial_hard_gate_pass_v1": False,
                "selected_allatom_commercial_overall_score_v1": 54.7,
                "selected_allatom_commercial_risk_bucket_v1": "high",
                "selected_allatom_commercial_decision_class_v1": "commercial_review_only",
                "selected_allatom_commercial_primary_upgrade_actions_v1": ["tighten_pose_geometry_under_strict_gate"],
                "selected_allatom_best_compound_name": "chembl_cache_e6069e85050b",
                "selected_allatom_best_compound_name_human_readable": "",
                "selected_allatom_best_compound_name_resolution": "cache_placeholder",
                "selected_allatom_best_mean_min_distance_A": 3.705,
                "selected_allatom_promoted_candidate_count": 4,
                "selected_allatom_under_2p5_candidate_count": 0,
                "selected_allatom_near_candidate_count": 2,
                "selected_allatom_next_required_step": (
                    "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
                    "and do not treat this rescue-only packet as wetlab-ready because the strict_only gate did not pass. "
                    "translation_gate=fail shortlist_tier=defer recommended_next_expensive_lane=defer_expensive_lane"
                ),
            }
        },
        broad_screen_current_results_index={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_best_mean_min_distance_A": 3.375,
                "selected_allatom_best_mean_min_distance_A_source": (
                    "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
                ),
                "selected_allatom_wetlab_gate_pass": False,
                "selected_allatom_final_gate_pass": False,
            }
        },
        broad_screen_selected_allatom_visual_bundle={
            "summary": {
                "status": "selected_allatom_visual_bundle_ready",
                "target_id": "T. cruzi PDE",
                "assets_dir": "/tmp/pde_visuals",
                "dashboard_html": "/tmp/pde_visuals/dashboard.html",
                "primary_figure_path": "/tmp/pde_visuals/hero.png",
                "primary_movie_script_path": "/tmp/pde_visuals/hero.cxc",
                "primary_movie_mp4_path": "/tmp/pde_visuals/hero.mp4",
                "topk_count": 4,
                "figure_count": 2,
                "movie_plan_count": 4,
                "binding_event_candidate_count": 4,
                "human_summary": "PDE visual rollup for partnering.",
            }
        },
    )
    summary = payload["summary"]
    assert summary["selected_allatom_target_id"] == "T. cruzi PDE"
    assert summary["selected_allatom_commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["selected_allatom_commercial_overall_score_v1"] == 54.7
    assert summary["selected_allatom_commercial_decision_class_v1"] == "commercial_review_only"
    assert summary["selected_allatom_commercial_schema_version_v2"] == ""
    assert summary["selected_allatom_commercial_provenance_mode_v2"] == "not_reported"
    assert summary["selected_allatom_commercial_human_summary_v2"] == (
        "Commercial-grade v2 is not yet reported for this focus."
    )
    assert summary["selected_allatom_best_mean_min_distance_A"] == 3.375
    assert summary["selected_allatom_best_mean_min_distance_A_source"] == (
        "tcruzi_pde_allatom_review_packet.best_mean_min_distance_A"
    )
    assert summary["selected_allatom_wetlab_gate_pass"] is False
    assert summary["selected_allatom_final_gate_pass"] is False
    assert summary["selected_allatom_raw_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_raw_claim_requirement_provenance"] == "claim_gate_required_for_final_wetlab"
    assert summary["selected_allatom_raw_claim_required_for_final_wetlab"] is True
    assert summary["selected_allatom_raw_claim_required_for_commercial_readiness"] is False
    assert summary["selected_allatom_raw_claim_requirement_reason"].startswith(
        "claim/equivalence gate is required"
    )
    assert summary["selected_allatom_effective_actionability_status"] == "hard_blocked"
    assert summary["selected_allatom_effective_actionability_claim_requirement_mode"] == "semi_hard"
    assert summary["selected_allatom_effective_actionability_claim_requirement_status"] == "blocked"
    assert summary["selected_allatom_effective_actionability_claim_requirement_reason"].startswith(
        "claim/equivalence gate is semi-hard"
    )
    assert summary["selected_allatom_effective_actionability_next_expensive_lane"] == "defer_expensive_lane"
    assert summary["selected_allatom_effective_actionability_next_expensive_lane_reason"].startswith(
        "translation gate is blocked"
    )
    assert summary["selected_allatom_effective_actionability_required_calculations"] == [
        "recompute_mean_min_distance_A",
        "resolve_claim_equivalence_gate",
    ]
    assert summary["selected_allatom_effective_actionability_required_calculations_text"] == (
        "recompute_mean_min_distance_A, resolve_claim_equivalence_gate"
    )
    assert summary["selected_allatom_effective_actionability_action_list_text"].startswith(
        "hard:recompute_mean_min_distance_A[required]"
    )
    assert summary["selected_allatom_effective_blocking_order"] == "hard_block_first"
    assert summary["selected_allatom_effective_primary_blocking_domain"] == "translation_v2"
    assert summary["selected_allatom_action_recipe_codes"] == [
        "recompute_mean_min_distance_A",
        "resolve_claim_equivalence_gate",
        "defer_expensive_lane",
    ]
    assert summary["selected_allatom_action_recipe_rollup_text"].startswith(
        "recompute_mean_min_distance_A, resolve_claim_equivalence_gate, defer_expensive_lane"
    )
    assert summary["selected_allatom_translation_gate_version"] == "three_bead_to_allatom_translation_v1"
    assert summary["selected_allatom_translation_gate_focus_status"] == "fail"
    assert summary["selected_allatom_translation_gate_focus_score"] == 0.0
    assert summary["selected_allatom_translation_gate_focus_reason"] == ""
    assert summary["selected_allatom_focus_shortlist_tier"] == "defer"
    assert summary["selected_allatom_recommended_next_expensive_lane"] == "defer_expensive_lane"
    assert summary["selected_allatom_recommended_next_expensive_lane_reason"] == ""
    assert summary["selected_allatom_translation_provenance_mode"] == "inferred_from_partial_upstream"
    assert summary["selected_allatom_hybrid_policy"] == (
        "canonical_scores_source_only__translation_shortlist_labeled_fallback"
    )
    assert summary["selected_allatom_visual_bundle_ready"] is True
    assert summary["selected_allatom_visual_availability_rollup"] == (
        "top-k 4 | figures 2 | movie plans 4 | binding-event candidates 4"
    )
    assert summary["selected_allatom_visual_media_ready_rollup"] == (
        "dashboard ready | figure ready | movie scripts 0/4 | movie mp4 0/4 | binding-event clips 0/4"
    )
    assert summary["selected_allatom_visual_human_summary"] == "PDE visual rollup for partnering."
    assert "Raw claim requirement semi_hard" in summary["selected_allatom_human_summary"]
    assert "effective actionability hard_blocked" in summary["selected_allatom_human_summary"]
    assert summary["selected_allatom_translation_summary"].startswith(
        "Translation/shortlist fallback (inferred from partial upstream; three_bead_to_allatom_translation_v1): status fail"
    )

    md_path = tmp_path / "partnering_stack.md"
    mod._write_markdown(md_path, payload)
    markdown = md_path.read_text(encoding="utf-8")
    assert "selected_allatom_raw_claim_requirement_mode" in markdown
    assert "selected_allatom_effective_actionability_status" in markdown
    assert "selected_allatom_action_recipe_rollup_text" in markdown
    assert "selected_allatom_visual_availability_rollup" in markdown
    assert "selected_allatom_visual_human_summary" in markdown


def test_partnering_stack_selected_allatom_green_next_step_overrides_stale_retry_wording(monkeypatch) -> None:
    monkeypatch.setattr(
        mod.selected_allatom_canonical_mod,
        "resolve_selected_allatom_canonical",
        lambda **kwargs: {
            "raw_claim_requirement_mode": "semi_hard",
            "raw_claim_requirement_provenance": "claim_gate_required_for_final_wetlab",
            "raw_claim_required_for_final_wetlab": True,
            "raw_claim_required_for_commercial_readiness": True,
            "raw_claim_requirement_reason": "claim/equivalence gate is required before final wetlab release.",
            "effective_actionability_status": "ready",
            "effective_actionability_claim_requirement_mode": "semi_hard",
            "effective_actionability_claim_requirement_status": "satisfied",
            "effective_actionability_claim_requirement_reason": "claim/equivalence gate is satisfied.",
            "effective_actionability_next_expensive_lane": "defer_expensive_lane",
            "effective_actionability_next_expensive_lane_reason": "translation gate remains borderline; expensive lane deferred.",
            "effective_actionability_required_calculations": [],
            "effective_actionability_required_calculations_text": "",
            "effective_actionability_action_list": [
                {"severity": "soft", "action": "defer_expensive_lane", "status": "deferred", "lane": "defer_expensive_lane"}
            ],
            "effective_actionability_action_list_text": (
                "soft:defer_expensive_lane[deferred] lane=defer_expensive_lane"
            ),
            "effective_blocking_order": "ready",
            "effective_primary_blocking_domain": "none",
            "action_recipe_codes": ["defer_expensive_lane"],
            "action_recipe_rows": [
                {"severity": "soft", "action": "defer_expensive_lane", "status": "deferred", "lane": "defer_expensive_lane"}
            ],
            "action_recipe_rollup_text": (
                "defer_expensive_lane | soft:defer_expensive_lane[deferred] lane=defer_expensive_lane"
            ),
            "translation_gate_version": "three_bead_to_allatom_translation_v1",
            "translation_gate_focus_status": "borderline",
            "translation_gate_focus_score": 0.5,
            "translation_gate_focus_reason": "Borderline translation support.",
            "focus_shortlist_tier": "follow_up",
            "recommended_next_expensive_lane": "defer_expensive_lane",
            "recommended_next_expensive_lane_reason": "Expensive lane deferred.",
            "translation_provenance_mode": "source_driven",
            "commercial_provenance_mode_v2": "source_driven",
            "hybrid_policy": "canonical_scores_source_only__translation_shortlist_labeled_fallback",
            "human_summary": "Selected all-atom delivery P0 is green; broader/default wetlab lane remains closed.",
        },
    )
    empty = {"summary": {}}
    stale_next_step = (
        "Review the promoted PDE pseudo all-atom top-4 packet manually only, keep the default lane closed, "
        "and do not treat this rescue-only packet as wetlab-ready because the strict_only gate did not pass."
    )

    payload = mod.build_payload(
        *([empty] * 19),
        broad_screen_retry_handoff_summary={
            "summary": {
                "status": "wetlab_retry_handoff_summary_ready",
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_operator_review_ready_reported": True,
                "selected_allatom_operator_review_ready": True,
                "selected_allatom_wetlab_gate_reported": True,
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_reported": True,
                "selected_allatom_final_gate_pass": True,
                "selected_allatom_claim_gate_available_reported": True,
                "selected_allatom_claim_gate_available": True,
                "selected_allatom_claim_ready_for_allatom_reported": True,
                "selected_allatom_claim_ready_for_allatom": True,
                "selected_allatom_next_required_step": stale_next_step,
            }
        },
        broad_screen_current_results_index={
            "summary": {
                "selected_allatom_target_id": "T. cruzi PDE",
                "selected_allatom_surface_label": "tcruzi_pde_allatom_review_packet",
                "selected_allatom_wetlab_gate_reported": True,
                "selected_allatom_wetlab_gate_pass": True,
                "selected_allatom_final_gate_reported": True,
                "selected_allatom_final_gate_pass": True,
                "selected_allatom_claim_gate_available_reported": True,
                "selected_allatom_claim_gate_available": True,
                "selected_allatom_claim_ready_for_allatom_reported": True,
                "selected_allatom_claim_ready_for_allatom": True,
                "selected_allatom_translation_gate_focus_status": "borderline",
                "selected_allatom_recommended_next_expensive_lane": "defer_expensive_lane",
            }
        },
    )

    summary = payload["summary"]
    assert summary["selected_allatom_final_gate_pass"] is True
    assert summary["selected_allatom_claim_ready_for_allatom"] is True
    assert "delivery P0 is green" in summary["selected_allatom_next_required_step"]
    assert "broader/default wetlab lane remains closed" in summary["selected_allatom_next_required_step"]
    assert "translation gate remains borderline" in summary["selected_allatom_next_required_step"]
    assert "expensive lane deferred" in summary["selected_allatom_next_required_step"]
    assert summary["next_required_step"] == summary["selected_allatom_next_required_step"]
    assert "strict_only gate did not pass" not in summary["next_required_step"]
    assert "do not treat this rescue-only packet as wetlab-ready" not in summary["next_required_step"]


def test_build_wetlab_partnering_stack_main_wires_target_retry_inputs(monkeypatch, tmp_path) -> None:
    root = tmp_path / "root"
    cwd = tmp_path / "cwd"
    (cwd / "runs").mkdir(parents=True)
    cwd_artifact = cwd / mod.DEFAULT_OUT_JSON
    cwd_artifact.write_text('{"summary":{"status":"preexisting_cwd_artifact"}}\n', encoding="utf-8")
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(mod, "ROOT", root)
    captured: dict[str, object] = {}
    markdown_paths: list[object] = []
    original_build_payload = mod.build_payload

    def fake_load(path: str) -> dict[str, object]:
        return {"summary": {"source_path": path}}

    def fake_build_payload(*args, **kwargs):
        bound = inspect.signature(original_build_payload).bind(*args, **kwargs)
        captured.update(bound.arguments)
        return {"summary": {"status": "ok"}, "structured": {}, "rows": []}

    monkeypatch.setattr(mod, "_load_json", fake_load)
    monkeypatch.setattr(mod, "_maybe_load_json", fake_load)
    monkeypatch.setattr(mod, "_write_markdown", lambda path, payload: markdown_paths.append(path))
    monkeypatch.setattr(mod, "build_payload", fake_build_payload)
    monkeypatch.setattr(sys, "argv", ["build_wetlab_partnering_stack.py"])

    mod.main()

    assert json.loads(cwd_artifact.read_text(encoding="utf-8"))["summary"]["status"] == "preexisting_cwd_artifact"
    assert json.loads((root / mod.DEFAULT_OUT_JSON).read_text(encoding="utf-8"))["summary"]["status"] == "ok"
    assert markdown_paths == [root / mod.DEFAULT_OUT_MD]
    assert captured["broad_screen_tcruzi_pde_promoted_top4_review_packet"] == {
        "summary": {"source_path": mod.DEFAULT_BROAD_SCREEN_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON}
    }
    assert captured["broad_screen_tcruzi_pde_rescue_only_branch_summary"] == {
        "summary": {"source_path": mod.DEFAULT_BROAD_SCREEN_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON}
    }
    assert captured["broad_screen_kinase_retry_policy_templates"] == {
        "summary": {"source_path": mod.DEFAULT_BROAD_SCREEN_KINASE_RETRY_POLICY_TEMPLATES_JSON}
    }
    assert captured["broad_screen_target_retry_policy_templates"] == {
        "summary": {"source_path": mod.DEFAULT_BROAD_SCREEN_TARGET_RETRY_POLICY_TEMPLATES_JSON}
    }
