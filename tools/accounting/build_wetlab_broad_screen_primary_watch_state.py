#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any

from tools import build_wetlab_broad_screen_throughput_bridge as bridge_mod
from tools.wetlab_broad_screen_watch_utils import (
    canonicalize_preferred_summary,
    first_ready_row,
    detect_throughput_summary,
    primary_active_row,
    primary_bridge_paths,
    process_alive,
    throughput_failed,
    throughput_ok,
)
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
TARGET_STK17B = "STK17B (DRAK2)"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_STK17B_EXPLORATORY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_broad_screen_primary_watch_state_current.md"


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _parse_iso_local(value: Any) -> dt.datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def _summary_is_fresh_for_active_row(summary_json_path: str, active_row: dict[str, Any]) -> bool:
    path = Path(summary_json_path)
    if not path.exists():
        return False
    started_at = _parse_iso_local(active_row.get("progress_started_at", ""))
    if started_at is None:
        return True
    try:
        summary_mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        return False
    return summary_mtime >= started_at


def _shard_number(shard_id: str) -> int:
    head = _text(shard_id).split("_of_", 1)[0]
    return int(head) if head.isdigit() else 0


def _resolved_rows_for_target(
    execution_queue_payload: dict[str, Any],
    *,
    target_id: str,
    before_shard_id: str = "",
) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in (execution_queue_payload.get("rows", []) or [])
        if _text(row.get("target_id")) == _text(target_id)
        and _text(row.get("queue_status")) in {"explicit_hold", "result_ready"}
    ]
    rows.sort(key=lambda row: _shard_number(_text(row.get("shard_id"))))
    if not before_shard_id:
        return rows
    cutoff = _shard_number(before_shard_id)
    return [row for row in rows if _shard_number(_text(row.get("shard_id"))) < cutoff]


def _traj_prod_diagnostics(summary_payload: dict[str, Any]) -> dict[str, Any]:
    traj_prod = dict(summary_payload.get("traj_prod", {}) or {})
    if traj_prod:
        return traj_prod
    stage2 = dict((summary_payload.get("stages", {}) or {}).get("stage2_trajectory_generation", {}) or {})
    traj_prod = dict(stage2.get("traj_prod", {}) or {})
    if traj_prod:
        return traj_prod
    diag = dict(stage2.get("traj_stage2_preset_diagnostics", {}) or {})
    if diag:
        return diag
    service = dict(summary_payload.get("service_result", {}) or {})
    diag = dict(service.get("traj_prod_stage2_preset_diagnostics", {}) or {})
    return diag


def _preset_mismatch_from_summary(summary_payload: dict[str, Any]) -> dict[str, Any]:
    diag = _traj_prod_diagnostics(summary_payload)
    requested = _text(diag.get("requested_preset") or diag.get("requested"))
    resolved = _text(diag.get("resolved_preset") or diag.get("resolved"))
    hinted = [str(value).strip() for value in (diag.get("hinted_families") or diag.get("detected_families") or []) if str(value).strip()]
    warnings = [str(value).strip() for value in (diag.get("warnings") or []) if str(value).strip()]
    effective = resolved or requested
    mismatch = bool(effective and hinted and effective not in hinted)
    return {
        "mismatch": mismatch,
        "requested_preset": requested,
        "resolved_preset": resolved,
        "hinted_families": hinted,
        "warnings": warnings,
    }


def detect_preset_mismatch_hard_guard(
    execution_queue_payload: dict[str, Any],
    compound_universe_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    *,
    target_native_csv: str = DEFAULT_TARGET_NATIVE_CSV,
) -> dict[str, Any]:
    ready_row = first_ready_row(execution_queue_payload, target_key="target_id", shard_key="shard_id")
    target_id = _text(ready_row.get("target_id"))
    shard_id = _text(ready_row.get("shard_id"))
    if not target_id or not shard_id:
        return {}
    previous_rows = _resolved_rows_for_target(execution_queue_payload, target_id=target_id, before_shard_id=shard_id)
    if not previous_rows:
        return {}
    previous_row = previous_rows[-1]
    previous_shard_id = _text(previous_row.get("shard_id"))
    bridge_payload = bridge_mod.build_payload(
        execution_queue=execution_queue_payload,
        compound_universe=compound_universe_payload,
        portfolio=portfolio_payload,
        target_native_csv=target_native_csv,
        target_id=target_id,
        shard_id=previous_shard_id,
    )
    paths = primary_bridge_paths(bridge_payload)
    canonicalize_preferred_summary(paths)
    summary_payload, detected_summary_json = detect_throughput_summary(paths)
    if not summary_payload:
        return {}
    service = dict(summary_payload.get("service_result", {}) or {})
    failed_stage = _text(service.get("failed_stage") or summary_payload.get("failed_stage"))
    if failed_stage != "stage6_operational_gate":
        return {}
    mismatch_diag = _preset_mismatch_from_summary(summary_payload)
    if not mismatch_diag.get("mismatch", False):
        return {}
    effective = mismatch_diag.get("resolved_preset") or mismatch_diag.get("requested_preset") or "explicit_preset"
    hinted = mismatch_diag.get("hinted_families") or ["default"]
    return {
        "active": True,
        "target_id": target_id,
        "blocked_shard_id": shard_id,
        "source_shard_id": previous_shard_id,
        "summary_json": detected_summary_json or paths.get("preferred_summary_json", ""),
        "requested_preset": mismatch_diag.get("requested_preset", ""),
        "resolved_preset": mismatch_diag.get("resolved_preset", ""),
        "hinted_families": hinted,
        "reason": (
            f"Default auto-start is hard-blocked for {target_id} {shard_id}; "
            f"the previous shard {previous_shard_id} failed stage6 after explicit preset {effective} "
            f"did not match detected target-family hints {hinted}. Route this target through a rescue or reviewed retry lane instead."
        ),
        "warnings": mismatch_diag.get("warnings", []),
    }


def detect_hard_target_rescue_lane(
    execution_queue_payload: dict[str, Any],
    rescue_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane_payload = rescue_lane_payload or maybe_load_json(DEFAULT_HARD_TARGET_RESCUE_LANE_JSON) or {}
    ready_row = first_ready_row(execution_queue_payload, target_key="target_id", shard_key="shard_id")
    ready_target = _text(ready_row.get("target_id"))
    ready_shard = _text(ready_row.get("shard_id"))
    if not ready_target or not ready_shard:
        return {}
    rows = [dict(row) for row in (lane_payload.get("rows", []) or [])]
    if not rows:
        return {}
    for row in rows:
        if _text(row.get("target_id")) == ready_target and _text(row.get("shard_id")) == ready_shard:
            return row
    for row in rows:
        if _text(row.get("target_id")) == ready_target:
            return row
    return {}


def _stage2_preset_diagnostics(summary_payload: dict[str, Any]) -> dict[str, Any]:
    stages = dict(summary_payload.get("stages", {}) or {})
    stage2 = dict(stages.get("stage2_trajectory_generation", {}) or {})
    diagnostics = dict(stage2.get("traj_stage2_preset_diagnostics", {}) or {})
    prod = dict(stage2.get("traj_prod", {}) or {})
    settings = dict(stage2.get("traj_stage2_settings", {}) or {})
    preset_settings = dict(settings.get("traj_prod_stage2_preset", {}) or {})
    requested = _text(diagnostics.get("requested")) or _text(prod.get("requested_preset")) or _text(preset_settings.get("requested"))
    resolved = _text(diagnostics.get("resolved")) or _text(prod.get("resolved_preset")) or _text(preset_settings.get("resolved"))
    hinted = diagnostics.get("hinted_families", prod.get("hinted_families", []))
    hinted_families = [str(item).strip() for item in hinted if str(item).strip()]
    warnings = [str(item).strip() for item in diagnostics.get("warnings", []) if str(item).strip()]
    mismatch_detected = bool(
        requested
        and hinted_families
        and requested not in {"auto", "default"}
        and requested not in hinted_families
        and any("does not match detected target-family hints" in warning for warning in warnings)
    )
    return {
        "requested_preset": requested,
        "resolved_preset": resolved,
        "hinted_families": hinted_families,
        "warnings": warnings,
        "mismatch_detected": mismatch_detected,
        "hard_guard_reason": (
            f"Requested preset {requested} does not match detected target-family hints {hinted_families}; block default-lane auto-start and require a target-specific rescue decision."
            if mismatch_detected
            else ""
        ),
    }


def detect_exploratory_hard_freeze(
    execution_queue_payload: dict[str, Any],
    exploratory_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lane_payload = (
        exploratory_lane_payload
        or maybe_load_json(DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
        or maybe_load_json(DEFAULT_STK17B_EXPLORATORY_LANE_JSON)
        or {}
    )
    lane_summary = dict((lane_payload or {}).get("summary", {}) or {})
    if _text(lane_summary.get("target_id")) != TARGET_STK17B:
        return {}
    if not bool(lane_summary.get("ready_for_manual_retry", False)):
        return {}
    selected_kind = _text(lane_summary.get("selected_command_kind"))
    if "gate45" not in selected_kind:
        return {}
    success_shard_id = _text(lane_summary.get("success_anchor_shard_id")) or _text(lane_summary.get("shard_id"))
    blocked_shard_id = _text(lane_summary.get("blocked_standard_auto_shard_id"))
    ready_row = first_ready_row(execution_queue_payload, target_key="target_id", shard_key="shard_id")
    ready_target = _text(ready_row.get("target_id"))
    ready_shard = _text(ready_row.get("shard_id"))
    if ready_target != TARGET_STK17B or not ready_shard:
        return {}
    if blocked_shard_id and ready_shard != blocked_shard_id:
        return {}
    if _shard_number(ready_shard) <= _shard_number(success_shard_id):
        return {}
    return {
        "active": True,
        "target_id": TARGET_STK17B,
        "success_shard_id": success_shard_id,
        "blocked_shard_id": ready_shard,
        "lane_label": _text(lane_summary.get("lane_label")) or "exploratory_gate45_followup_retry",
        "selected_command_kind": selected_kind,
        "reason": (
            f"Default auto-start is frozen for {TARGET_STK17B} follow-up shard {ready_shard}; "
            f"the exploratory gate4.5 follow-up lane anchored on {success_shard_id} must select follow-up shards explicitly."
        ),
    }


def build_payload(
    execution_queue_payload: dict[str, Any],
    compound_universe_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    *,
    target_native_csv: str = DEFAULT_TARGET_NATIVE_CSV,
    exploratory_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exploratory_freeze = detect_exploratory_hard_freeze(execution_queue_payload, exploratory_lane_payload)
    preset_mismatch_guard = detect_preset_mismatch_hard_guard(
        execution_queue_payload,
        compound_universe_payload,
        portfolio_payload,
        target_native_csv=target_native_csv,
    )
    rescue_lane = detect_hard_target_rescue_lane(execution_queue_payload)
    active = primary_active_row(execution_queue_payload)
    if not active:
        return {
            "summary": {
                "status": "wetlab_broad_screen_primary_watch_state_ready",
                "active_target_id": "",
                "active_shard_id": "",
                "active_queue_status": "",
                "watcher_decision": (
                    "idle_exploratory_hard_freeze_pending_followup"
                    if exploratory_freeze
                    else "idle_preset_mismatch_hard_guard_pending_review"
                    if preset_mismatch_guard
                    else "idle_hard_target_rescue_lane_pending_review"
                    if rescue_lane
                    else "idle_no_running_primary_row"
                ),
                "preset_mismatch_hard_guard_active": bool(preset_mismatch_guard),
                "preset_mismatch_hard_guard_target_id": _text(preset_mismatch_guard.get("target_id")),
                "preset_mismatch_hard_guard_source_shard_id": _text(preset_mismatch_guard.get("source_shard_id")),
                "preset_mismatch_hard_guard_blocked_shard_id": _text(preset_mismatch_guard.get("blocked_shard_id")),
                "preset_mismatch_hard_guard_reason": _text(preset_mismatch_guard.get("reason")),
                "preset_mismatch_hard_guard_requested_preset": _text(preset_mismatch_guard.get("requested_preset")),
                "preset_mismatch_hard_guard_resolved_preset": _text(preset_mismatch_guard.get("resolved_preset")),
                "hard_target_rescue_lane_active": bool(rescue_lane),
                "hard_target_rescue_target_id": _text(rescue_lane.get("target_id")),
                "hard_target_rescue_shard_id": _text(rescue_lane.get("shard_id")),
                "hard_target_rescue_selected_command_kind": _text(rescue_lane.get("selected_command_kind")),
                "hard_target_rescue_stage2_preset_override": _text(rescue_lane.get("stage2_preset_override")),
                "hard_target_rescue_anchor_artifact_required": bool(rescue_lane.get("anchor_artifact_required", False)),
                "hard_target_rescue_three_bead_recommended": bool(rescue_lane.get("three_bead_recommended", False)),
                "exploratory_hard_freeze_active": bool(exploratory_freeze),
                "exploratory_hard_freeze_target_id": _text(exploratory_freeze.get("target_id")),
                "exploratory_hard_freeze_success_shard_id": _text(exploratory_freeze.get("success_shard_id")),
                "exploratory_hard_freeze_blocked_shard_id": _text(exploratory_freeze.get("blocked_shard_id")),
                "exploratory_hard_freeze_reason": _text(exploratory_freeze.get("reason")),
                "next_required_step": (
                    _text(exploratory_freeze.get("reason"))
                    if exploratory_freeze
                    else _text(rescue_lane.get("next_required_step"))
                    if rescue_lane
                    else _text(preset_mismatch_guard.get("reason"))
                    if preset_mismatch_guard
                    else "No running primary broad-screen row is active; dispatch a ready shard or wait for auto-start."
                ),
            },
            "rows": [
                {
                    "hard_target_rescue_lane_active": bool(rescue_lane),
                    "hard_target_rescue_target_id": _text(rescue_lane.get("target_id")),
                    "hard_target_rescue_shard_id": _text(rescue_lane.get("shard_id")),
                    "hard_target_rescue_selected_command_kind": _text(rescue_lane.get("selected_command_kind")),
                    "hard_target_rescue_stage2_preset_override": _text(rescue_lane.get("stage2_preset_override")),
                    "hard_target_rescue_anchor_artifact_required": bool(rescue_lane.get("anchor_artifact_required", False)),
                    "hard_target_rescue_three_bead_recommended": bool(rescue_lane.get("three_bead_recommended", False)),
                    "preset_mismatch_hard_guard_active": bool(preset_mismatch_guard),
                    "preset_mismatch_hard_guard_target_id": _text(preset_mismatch_guard.get("target_id")),
                    "preset_mismatch_hard_guard_source_shard_id": _text(preset_mismatch_guard.get("source_shard_id")),
                    "preset_mismatch_hard_guard_blocked_shard_id": _text(preset_mismatch_guard.get("blocked_shard_id")),
                    "preset_mismatch_hard_guard_reason": _text(preset_mismatch_guard.get("reason")),
                    "exploratory_hard_freeze_active": bool(exploratory_freeze),
                    "exploratory_hard_freeze_target_id": _text(exploratory_freeze.get("target_id")),
                    "exploratory_hard_freeze_success_shard_id": _text(exploratory_freeze.get("success_shard_id")),
                    "exploratory_hard_freeze_blocked_shard_id": _text(exploratory_freeze.get("blocked_shard_id")),
                    "exploratory_hard_freeze_reason": _text(exploratory_freeze.get("reason")),
                }
            ],
        }

    target_id = str(active.get("target_id", "")).strip()
    shard_id = str(active.get("shard_id", "")).strip()
    bridge_payload = bridge_mod.build_payload(
        execution_queue=execution_queue_payload,
        compound_universe=compound_universe_payload,
        portfolio=portfolio_payload,
        target_native_csv=target_native_csv,
        target_id=target_id,
        shard_id=shard_id,
    )
    paths = primary_bridge_paths(bridge_payload)
    canonicalize_preferred_summary(paths)
    summary_payload, detected_summary_json = detect_throughput_summary(paths)
    if summary_payload and not _summary_is_fresh_for_active_row(detected_summary_json or paths["preferred_summary_json"], active):
        summary_payload = {}
        detected_summary_json = ""
    pid_alive, pid_value = process_alive(paths["preferred_pid_path"]) if paths["preferred_pid_path"] else (False, 0)
    heartbeat_pid_path = str(ROOT / "runs" / "wetlab_broad_screen_heartbeat_loop.pid")
    heartbeat_pid_alive, heartbeat_pid_value = process_alive(heartbeat_pid_path)
    stage2_diag = _stage2_preset_diagnostics(summary_payload)

    if throughput_ok(summary_payload):
        decision = "auto_complete_candidate_summary_ok"
    elif throughput_failed(summary_payload):
        decision = "auto_hold_candidate_summary_failed"
    elif paths["preferred_pid_path"] and pid_value and not pid_alive:
        decision = "auto_hold_candidate_pid_exited_no_summary"
    elif paths["preferred_pid_path"] and pid_alive:
        decision = "continue_running_compute_alive"
    else:
        decision = "continue_running_no_pid_only_progress"

    service = dict(summary_payload.get("service_result", {}) or {})
    raw_failed_stage = summary_payload.get("failed_stage", service.get("failed_stage", ""))
    failed_stage = "" if raw_failed_stage in {None, ""} else str(raw_failed_stage).strip()
    return {
        "summary": {
            "status": "wetlab_broad_screen_primary_watch_state_ready",
            "active_target_id": target_id,
            "active_shard_id": shard_id,
            "active_queue_status": str(active.get("queue_status", "")).strip(),
            "preferred_command_kind": paths["preferred_command_kind"],
            "compute_pid_path": paths["preferred_pid_path"],
            "compute_pid": pid_value,
            "compute_pid_alive": pid_alive,
            "heartbeat_pid_path": heartbeat_pid_path,
            "heartbeat_pid": heartbeat_pid_value,
            "heartbeat_pid_alive": heartbeat_pid_alive,
            "throughput_summary_json": detected_summary_json or paths["preferred_summary_json"],
            "throughput_summary_detected": bool(summary_payload),
            "throughput_status": str(service.get("status", "")).strip(),
            "throughput_error_code": str(service.get("error_code", "")).strip(),
            "throughput_failed_stage": failed_stage,
            "stage2_requested_preset": stage2_diag["requested_preset"],
            "stage2_resolved_preset": stage2_diag["resolved_preset"],
            "stage2_hinted_families": "; ".join(stage2_diag["hinted_families"]),
            "stage2_preset_warning_count": len(stage2_diag["warnings"]),
            "preset_mismatch_hard_guard_active": stage2_diag["mismatch_detected"],
            "preset_mismatch_hard_guard_reason": stage2_diag["hard_guard_reason"],
            "exploratory_hard_freeze_active": bool(exploratory_freeze),
            "exploratory_hard_freeze_target_id": _text(exploratory_freeze.get("target_id")),
            "exploratory_hard_freeze_success_shard_id": _text(exploratory_freeze.get("success_shard_id")),
            "exploratory_hard_freeze_blocked_shard_id": _text(exploratory_freeze.get("blocked_shard_id")),
            "exploratory_hard_freeze_reason": _text(exploratory_freeze.get("reason")),
            "watcher_decision": decision,
            "next_required_step": (
                stage2_diag["hard_guard_reason"]
                if stage2_diag["mismatch_detected"] and decision.startswith("auto_hold_candidate")
                else
                f"Complete {target_id} {shard_id} automatically and consider auto-starting the next primary shard."
                if decision == "auto_complete_candidate_summary_ok"
                else f"Hold {target_id} {shard_id} and inspect the throughput summary."
                if decision.startswith("auto_hold_candidate")
                else f"Keep monitoring {target_id} {shard_id} until compute finishes."
            ),
        },
        "structured": {
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "progress_artifact": "runs/wetlab_broad_screen_progress_current.md",
            "preferred_log_path": paths["preferred_log_path"],
            "preferred_out_prefix": paths["preferred_out_prefix"],
        },
        "rows": [
            {
                "target_id": target_id,
                "shard_id": shard_id,
                "queue_status": str(active.get("queue_status", "")).strip(),
                "watcher_decision": decision,
                "compute_pid_alive": pid_alive,
                "compute_pid": pid_value,
                "heartbeat_pid": heartbeat_pid_value,
                "heartbeat_pid_alive": heartbeat_pid_alive,
                "throughput_summary_detected": bool(summary_payload),
                "throughput_failed": throughput_failed(summary_payload),
                "throughput_ok": throughput_ok(summary_payload),
                "preferred_command_kind": paths["preferred_command_kind"],
                "stage2_requested_preset": stage2_diag["requested_preset"],
                "stage2_resolved_preset": stage2_diag["resolved_preset"],
                "stage2_hinted_families": "; ".join(stage2_diag["hinted_families"]),
                "preset_mismatch_hard_guard_active": stage2_diag["mismatch_detected"],
                "preset_mismatch_hard_guard_reason": stage2_diag["hard_guard_reason"],
                "exploratory_hard_freeze_active": bool(exploratory_freeze),
                "exploratory_hard_freeze_blocked_shard_id": _text(exploratory_freeze.get("blocked_shard_id")),
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build current watcher state for the active primary broad-screen row.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Broad Screen Primary Watch State",
        build_payload(
            load_json(args.execution_queue_json),
            load_json(args.compound_universe_json),
            maybe_load_json(args.portfolio_json) or load_json(args.portfolio_json),
            target_native_csv=args.target_native_csv,
            exploratory_lane_payload=(
                maybe_load_json(DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
                or maybe_load_json(DEFAULT_STK17B_EXPLORATORY_LANE_JSON)
                or {}
            ),
        ),
    )
