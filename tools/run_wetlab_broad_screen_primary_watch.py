#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_primary_watch_state as state_mod
from tools import run_wetlab_broad_screen_runtime_event as runtime_mod
from tools import run_wetlab_broad_screen_primary_runner as runner_mod
from tools.wetlab_broad_screen_watch_utils import (
    consecutive_auto_hold_streak,
    first_ready_row,
    primary_active_row,
    stop_pid_file,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_primary_watch_action_current.md"
DEFAULT_HEARTBEAT_PID = "runs/wetlab_broad_screen_heartbeat_loop.pid"
DEFAULT_MAX_CONSECUTIVE_AUTO_HOLDS = 3
POST_ACTION_SCRIPTS = [
    "tools/build_wetlab_broad_screen_throughput_bridge.py",
    "tools/build_wetlab_broad_screen_precision_monitor.py",
    "tools/build_wetlab_primary_hold_guard_surface.py",
    "tools/build_wetlab_primary_stage6_failure_surface.py",
    "tools/build_wetlab_primary_retry_preset_surface.py",
    "tools/build_wetlab_hard_target_rescue_lane.py",
    "tools/build_wetlab_rescue_anchor_artifacts.py",
    "tools/build_wetlab_rescue_three_bead_candidates.py",
    "tools/build_wetlab_kinase_retry_policy_templates.py",
    "tools/build_wetlab_cathepsin_k_stage6_tuning_surface.py",
    "tools/build_wetlab_cathepsin_k_exploratory_retry_lane.py",
    "tools/build_wetlab_sarscov2_mpro_stage6_tuning_surface.py",
    "tools/build_wetlab_sarscov2_mpro_exploratory_retry_lane.py",
    "tools/build_wetlab_tcruzi_pde_stage6_tuning_surface.py",
    "tools/build_wetlab_tcruzi_pde_exploratory_retry_lane.py",
    "tools/build_wetlab_target_retry_policy_templates.py",
    "tools/build_wetlab_mapping_fix_retry_policy_templates.py",
    "tools/build_wetlab_stk17b_manual_retry_lane.py",
    "tools/build_wetlab_stk17b_exploratory_retry_lane.py",
    "tools/build_wetlab_stk17b_exploratory_trace.py",
    "tools/build_wetlab_stk17b_exploratory_followup_lane.py",
    "tools/build_wetlab_stk17b_followup_review_surface.py",
    "tools/build_wetlab_retry_handoff_summary.py",
    "tools/build_wetlab_monitor_semantics.py",
    "tools/build_wetlab_current_results_index.py",
    "tools/build_wetlab_final_campaign_summary.py",
    "tools/build_wetlab_master_handoff_dashboard.py",
    "tools/build_wetlab_partnering_stack.py",
]


def _post_refresh(python_bin: str) -> None:
    for script in POST_ACTION_SCRIPTS:
        subprocess.run([python_bin, str(ROOT / script)], cwd=ROOT, check=True)


def _complete_running_row(*, target_id: str, shard_id: str, python_bin: str, note: str, stage_label: str, compute_pid_path: str = "") -> None:
    if compute_pid_path:
        stop_pid_file(compute_pid_path)
    stop_pid_file(DEFAULT_HEARTBEAT_PID)
    runtime_mod.run_event(
        target_id=target_id,
        shard_id=shard_id,
        event="complete",
        python_bin=python_bin,
        active_stage_label=stage_label,
        notes=note,
    )


def _hold_running_row(*, target_id: str, shard_id: str, python_bin: str, note: str, stage_label: str, compute_pid_path: str = "") -> None:
    if compute_pid_path:
        stop_pid_file(compute_pid_path)
    stop_pid_file(DEFAULT_HEARTBEAT_PID)
    runtime_mod.run_event(
        target_id=target_id,
        shard_id=shard_id,
        event="hold",
        python_bin=python_bin,
        active_stage_label=stage_label,
        notes=note,
    )


def run_once(
    *,
    python_bin: str,
    execution_queue_json: str,
    compound_universe_json: str,
    portfolio_json: str,
    target_native_csv: str,
    auto_start_next: bool,
    max_consecutive_auto_holds: int = DEFAULT_MAX_CONSECUTIVE_AUTO_HOLDS,
) -> dict[str, Any]:
    execution_queue = load_json(execution_queue_json)
    compound_universe = load_json(compound_universe_json)
    portfolio = maybe_load_json(portfolio_json) or load_json(portfolio_json)

    watch_state = state_mod.build_payload(
        execution_queue,
        compound_universe,
        portfolio,
        target_native_csv=target_native_csv,
    )
    summary = dict(watch_state.get("summary", {}) or {})
    target_id = str(summary.get("active_target_id", "")).strip()
    shard_id = str(summary.get("active_shard_id", "")).strip()
    decision = str(summary.get("watcher_decision", "")).strip()
    compute_pid_path = str(summary.get("compute_pid_path", "")).strip()
    active_row = primary_active_row(execution_queue)
    stage_label = str(active_row.get("active_stage_label", "")).strip() or "broad_screen_primary_shard"
    active_notes = str(active_row.get("notes", "")).strip()
    action_taken = "noop"
    guard_blocked_target = ""
    guard_hold_streak = 0
    preset_mismatch_guard_blocked_target = ""
    preset_mismatch_guard_requested_preset = ""
    preset_mismatch_guard_hinted_families = ""
    preset_mismatch_guard_reason = ""
    rescue_lane_blocked_target = ""
    rescue_lane_blocked_shard = ""
    rescue_lane_selected_command_kind = ""
    rescue_lane_stage2_preset_override = ""
    rescue_lane_reason = ""
    exploratory_success_freeze_target = ""
    exploratory_success_freeze_shard = ""
    exploratory_hard_freeze_reason = ""
    exploratory_hard_freeze_blocked_shard = ""
    exploratory_success = False
    preset_mismatch_hard_guard_target = ""
    preset_mismatch_hard_guard_source_shard = ""
    preset_mismatch_hard_guard_blocked_shard = ""
    preset_mismatch_hard_guard_reason = ""

    if decision == "auto_complete_candidate_summary_ok" and target_id and shard_id:
        exploratory_success = (
            "tuned_gate45" in stage_label
            or "throughput_preflight_tuned_gate45" in active_notes
            or "throughput_execute_tuned_gate45" in active_notes
        )
        _complete_running_row(
            target_id=target_id,
            shard_id=shard_id,
            python_bin=python_bin,
            note="auto_complete_from_summary_watcher_runtime_validation_only",
            stage_label=stage_label,
            compute_pid_path=compute_pid_path,
        )
        action_taken = "completed_from_summary"
    elif decision.startswith("auto_hold_candidate") and target_id and shard_id:
        _hold_running_row(
            target_id=target_id,
            shard_id=shard_id,
            python_bin=python_bin,
            note="auto_hold_from_primary_watcher_runtime_validation_only",
            stage_label=stage_label,
            compute_pid_path=compute_pid_path,
        )
        action_taken = "held_from_watcher"

    if action_taken != "noop":
        _post_refresh(python_bin)
        execution_queue = load_json(execution_queue_json)

    autostart_target = ""
    autostart_shard = ""
    if auto_start_next:
        active = primary_active_row(execution_queue)
        if exploratory_success and target_id:
            exploratory_success_freeze_target = target_id
            exploratory_success_freeze_shard = shard_id
            exploratory_freeze = state_mod.detect_exploratory_hard_freeze(execution_queue)
            exploratory_hard_freeze_blocked_shard = str(exploratory_freeze.get("blocked_shard_id", "")).strip()
            exploratory_hard_freeze_reason = str(exploratory_freeze.get("reason", "")).strip()
            action_taken = (
                f"{action_taken}+freeze_after_exploratory_success"
                if action_taken != "noop"
                else "freeze_after_exploratory_success"
            )
            if exploratory_hard_freeze_reason:
                action_taken = f"{action_taken}+hard_freeze_default_autostart"
        elif not active:
            exploratory_freeze = state_mod.detect_exploratory_hard_freeze(execution_queue)
            if exploratory_freeze:
                exploratory_success_freeze_target = str(exploratory_freeze.get("target_id", "")).strip()
                exploratory_success_freeze_shard = str(exploratory_freeze.get("success_shard_id", "")).strip()
                exploratory_hard_freeze_blocked_shard = str(exploratory_freeze.get("blocked_shard_id", "")).strip()
                exploratory_hard_freeze_reason = str(exploratory_freeze.get("reason", "")).strip()
                action_taken = (
                    f"{action_taken}+hard_freeze_default_autostart"
                    if action_taken != "noop"
                    else "hard_freeze_default_autostart"
                )
                autostart_target = ""
                autostart_shard = ""
                ready_row = {}
            else:
                preset_guard = state_mod.detect_preset_mismatch_hard_guard(
                    execution_queue,
                    compound_universe,
                    portfolio,
                    target_native_csv=target_native_csv,
                )
                if preset_guard:
                    preset_mismatch_hard_guard_target = str(preset_guard.get("target_id", "")).strip()
                    preset_mismatch_hard_guard_source_shard = str(preset_guard.get("source_shard_id", "")).strip()
                    preset_mismatch_hard_guard_blocked_shard = str(preset_guard.get("blocked_shard_id", "")).strip()
                    preset_mismatch_hard_guard_reason = str(preset_guard.get("reason", "")).strip()
                ready_row = first_ready_row(execution_queue, target_key="target_id", shard_key="shard_id")
            autostart_target = str(ready_row.get("target_id", "")).strip()
            autostart_shard = str(ready_row.get("shard_id", "")).strip()
            rescue_lane_active = bool(summary.get("hard_target_rescue_lane_active", False))
            preset_mismatch_active = bool(summary.get("preset_mismatch_hard_guard_active", False))
            preset_mismatch_summary_target = str(
                summary.get("preset_mismatch_hard_guard_target_id", "") or summary.get("active_target_id", "")
            ).strip()
            preset_mismatch_summary_blocked_shard = str(
                summary.get("preset_mismatch_hard_guard_blocked_shard_id", "") or autostart_shard
            ).strip()
            preset_mismatch_target_matches = bool(
                autostart_target
                and autostart_shard
                and (
                    (
                        preset_mismatch_active
                        and autostart_target == preset_mismatch_summary_target
                        and autostart_shard == preset_mismatch_summary_blocked_shard
                    )
                    or (
                        preset_mismatch_hard_guard_target
                        and autostart_target == preset_mismatch_hard_guard_target
                        and autostart_shard == preset_mismatch_hard_guard_blocked_shard
                    )
                )
            )
            rescue_lane_matches = bool(
                rescue_lane_active
                and autostart_target
                and autostart_shard
                and autostart_target == str(summary.get("hard_target_rescue_target_id", "")).strip()
                and autostart_shard == str(summary.get("hard_target_rescue_shard_id", "")).strip()
            )
            if autostart_target and autostart_shard:
                guard_hold_streak = consecutive_auto_hold_streak(
                    execution_queue,
                    target_id=autostart_target,
                    before_shard_id=autostart_shard,
                )
                if max_consecutive_auto_holds > 0 and guard_hold_streak >= max_consecutive_auto_holds:
                    guard_blocked_target = autostart_target
            guard_triggered = (
                autostart_target
                and autostart_shard
                and max_consecutive_auto_holds > 0
                and guard_hold_streak >= max_consecutive_auto_holds
            )
            if guard_triggered:
                guard_blocked_target = autostart_target
                action_taken = (
                    f"{action_taken}+guard_stop_target_after_holds"
                    if action_taken != "noop"
                    else "guard_stop_target_after_holds"
                )
                autostart_target = ""
                autostart_shard = ""
            elif preset_mismatch_target_matches:
                preset_mismatch_guard_blocked_target = autostart_target
                preset_mismatch_guard_requested_preset = str(summary.get("preset_mismatch_hard_guard_requested_preset", "") or summary.get("stage2_requested_preset", "")).strip()
                preset_mismatch_guard_hinted_families = str(summary.get("stage2_hinted_families", "")).strip()
                preset_mismatch_guard_reason = str(summary.get("preset_mismatch_hard_guard_reason", "")).strip()
                action_taken = (
                    f"{action_taken}+preset_mismatch_hard_guard_block"
                    if action_taken != "noop"
                    else "preset_mismatch_hard_guard_block"
                )
                autostart_target = ""
                autostart_shard = ""
            elif rescue_lane_matches:
                rescue_lane_blocked_target = autostart_target
                rescue_lane_blocked_shard = autostart_shard
                rescue_lane_selected_command_kind = str(summary.get("hard_target_rescue_selected_command_kind", "")).strip()
                rescue_lane_stage2_preset_override = str(summary.get("hard_target_rescue_stage2_preset_override", "")).strip()
                rescue_lane_reason = str(summary.get("next_required_step", "")).strip()
                action_taken = (
                    f"{action_taken}+route_to_hard_target_rescue_lane"
                    if action_taken != "noop"
                    else "route_to_hard_target_rescue_lane"
                )
                autostart_target = ""
                autostart_shard = ""
            elif autostart_target and autostart_shard:
                runner_mod.run(
                    target_id=autostart_target,
                    shard_id=autostart_shard,
                    python_bin=python_bin,
                    command_kind="auto",
                    execution_queue_json=execution_queue_json,
                    compound_universe_json=compound_universe_json,
                    portfolio_json=portfolio_json,
                    target_native_csv=target_native_csv,
                    interval_sec=30.0,
                    replace_heartbeat=True,
                )
                _post_refresh(python_bin)
                action_taken = f"{action_taken}+autostart_next" if action_taken != "noop" else "autostart_next"

    payload = {
        "summary": {
            "status": "wetlab_broad_screen_primary_watch_action_ready",
            "watcher_decision": decision,
            "action_taken": action_taken,
            "active_target_id": target_id,
            "active_shard_id": shard_id,
            "autostart_target_id": autostart_target,
            "autostart_shard_id": autostart_shard,
            "guard_blocked_target_id": guard_blocked_target,
            "guard_hold_streak": guard_hold_streak,
            "guard_hold_limit": max_consecutive_auto_holds,
            "preset_mismatch_guard_blocked_target_id": preset_mismatch_guard_blocked_target,
            "preset_mismatch_guard_requested_preset": preset_mismatch_guard_requested_preset,
            "preset_mismatch_guard_hinted_families": preset_mismatch_guard_hinted_families,
            "preset_mismatch_guard_reason": preset_mismatch_guard_reason,
            "hard_target_rescue_blocked_target_id": rescue_lane_blocked_target,
            "hard_target_rescue_blocked_shard_id": rescue_lane_blocked_shard,
            "hard_target_rescue_selected_command_kind": rescue_lane_selected_command_kind,
            "hard_target_rescue_stage2_preset_override": rescue_lane_stage2_preset_override,
            "hard_target_rescue_reason": rescue_lane_reason,
            "exploratory_success_freeze_target_id": exploratory_success_freeze_target,
            "exploratory_success_freeze_shard_id": exploratory_success_freeze_shard,
            "exploratory_hard_freeze_blocked_shard_id": exploratory_hard_freeze_blocked_shard,
            "exploratory_hard_freeze_reason": exploratory_hard_freeze_reason,
            "preset_mismatch_hard_guard_target_id": preset_mismatch_hard_guard_target,
            "preset_mismatch_hard_guard_source_shard_id": preset_mismatch_hard_guard_source_shard,
            "preset_mismatch_hard_guard_blocked_shard_id": preset_mismatch_hard_guard_blocked_shard,
            "preset_mismatch_hard_guard_reason": preset_mismatch_hard_guard_reason,
            "next_required_step": (
                exploratory_hard_freeze_reason
                if exploratory_hard_freeze_reason
                else preset_mismatch_hard_guard_reason
                if preset_mismatch_hard_guard_reason
                else rescue_lane_reason
                if rescue_lane_blocked_target
                else f"Keep auto-start frozen after exploratory success for {exploratory_success_freeze_target} {exploratory_success_freeze_shard}; review the STK17B gate4.5 retry outcome before opening the next shard."
                if exploratory_success_freeze_target
                else
                preset_mismatch_guard_reason
                if preset_mismatch_guard_blocked_target
                else
                f"Pause auto-advance for {guard_blocked_target}; it hit {guard_hold_streak} consecutive auto-holds. Review the target-level gate-failure surface before continuing."
                if guard_blocked_target
                else "Run the primary watcher again or leave it in loop mode to keep queue state aligned with compute state."
            ),
        },
        "structured": {
            "watch_state_artifact": "runs/wetlab_broad_screen_primary_watch_state_current.md",
            "runner_artifact": "runs/wetlab_broad_screen_primary_runner_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        },
        "rows": [
            {
                "watcher_decision": decision,
                "action_taken": action_taken,
                "active_target_id": target_id,
                "active_shard_id": shard_id,
                "autostart_target_id": autostart_target,
                "autostart_shard_id": autostart_shard,
                "guard_blocked_target_id": guard_blocked_target,
                "guard_hold_streak": guard_hold_streak,
                "guard_hold_limit": max_consecutive_auto_holds,
                "preset_mismatch_guard_blocked_target_id": preset_mismatch_guard_blocked_target,
                "preset_mismatch_guard_requested_preset": preset_mismatch_guard_requested_preset,
                "preset_mismatch_guard_hinted_families": preset_mismatch_guard_hinted_families,
                "preset_mismatch_guard_reason": preset_mismatch_guard_reason,
                "hard_target_rescue_blocked_target_id": rescue_lane_blocked_target,
                "hard_target_rescue_blocked_shard_id": rescue_lane_blocked_shard,
                "hard_target_rescue_selected_command_kind": rescue_lane_selected_command_kind,
                "hard_target_rescue_stage2_preset_override": rescue_lane_stage2_preset_override,
                "hard_target_rescue_reason": rescue_lane_reason,
                "exploratory_success_freeze_target_id": exploratory_success_freeze_target,
                "exploratory_success_freeze_shard_id": exploratory_success_freeze_shard,
                "exploratory_hard_freeze_blocked_shard_id": exploratory_hard_freeze_blocked_shard,
                "exploratory_hard_freeze_reason": exploratory_hard_freeze_reason,
                "preset_mismatch_hard_guard_target_id": preset_mismatch_hard_guard_target,
                "preset_mismatch_hard_guard_source_shard_id": preset_mismatch_hard_guard_source_shard,
                "preset_mismatch_hard_guard_blocked_shard_id": preset_mismatch_hard_guard_blocked_shard,
                "preset_mismatch_hard_guard_reason": preset_mismatch_hard_guard_reason,
            }
        ],
    }
    write_artifact(DEFAULT_OUT_MD, "Wet-Lab Broad Screen Primary Watch Action", payload)
    subprocess.run([python_bin, str(ROOT / "tools/build_wetlab_broad_screen_primary_watch_state.py")], cwd=ROOT, check=True)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch the active primary broad-screen shard and auto-complete/advance when throughput artifacts are ready.")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--auto-start-next", action="store_true")
    parser.add_argument("--max-consecutive-auto-holds", type=int, default=DEFAULT_MAX_CONSECUTIVE_AUTO_HOLDS)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.loop:
        run_once(
            python_bin=args.python_bin,
            execution_queue_json=args.execution_queue_json,
            compound_universe_json=args.compound_universe_json,
            portfolio_json=args.portfolio_json,
            target_native_csv=args.target_native_csv,
            auto_start_next=args.auto_start_next,
            max_consecutive_auto_holds=args.max_consecutive_auto_holds,
        )
    else:
        while True:
            payload = run_once(
                python_bin=args.python_bin,
                execution_queue_json=args.execution_queue_json,
                compound_universe_json=args.compound_universe_json,
                portfolio_json=args.portfolio_json,
                target_native_csv=args.target_native_csv,
                auto_start_next=args.auto_start_next,
                max_consecutive_auto_holds=args.max_consecutive_auto_holds,
            )
            action_taken = str(payload.get("summary", {}).get("action_taken", "")).strip()
            if action_taken and action_taken != "noop":
                time.sleep(0.5)
            else:
                time.sleep(max(args.interval_sec, 1.0))
