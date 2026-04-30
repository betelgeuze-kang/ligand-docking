#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, resolve
from tools.wetlab_pose_validation_utils import build_pose_validation_fields_from_summary
from tools.wetlab_selected_allatom_canonical import (
    resolve_selected_allatom_canonical,
    selected_allatom_green_next_required_step,
)
from tools.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRIMARY_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_PRIMARY_WATCH_STATE_JSON = "runs/wetlab_broad_screen_primary_watch_state_current.json"
DEFAULT_ANTITARGET_WATCH_STATE_JSON = "runs/wetlab_broad_screen_antitarget_watcher_state_current.json"
DEFAULT_PRIMARY_WATCH_LOOP_PID = "runs/wetlab_broad_screen_primary_watch_loop.pid"
DEFAULT_ANTITARGET_WATCHER_LOOP_PID = "runs/wetlab_broad_screen_antitarget_watcher_loop.pid"
DEFAULT_PRECISION_MONITOR_JSON = "runs/wetlab_broad_screen_precision_monitor_current.json"
DEFAULT_FAILURE_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
DEFAULT_RETRY_PRESET_JSON = "runs/wetlab_broad_screen_throughput_bridge_current.json"
DEFAULT_ANTITARGET_RETRY_PRESET_JSON = "runs/wetlab_broad_screen_antitarget_throughput_bridge_current.json"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_broad_screen_primary_watch_action_current.json"
DEFAULT_RETRY_HANDOFF_JSON = "runs/wetlab_retry_handoff_summary_current.json"
DEFAULT_DPRE1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_dpre1_branch_review_surface_current.json"
DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_branch_review_surface_current.json"
DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.json"
DEFAULT_DENGUE_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.json"
DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_kinase_retry_policy_templates_current.json"
DEFAULT_TARGET_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON = "runs/wetlab_plpro_manual_retry_lane_current.json"
DEFAULT_MAPPING_FIX_RETRY_SUPPORT_JSON = "runs/wetlab_mapping_fix_retry_support_current.json"
DEFAULT_STAGE1_MAPPING_FIX_LANES_JSON = "runs/wetlab_stage1_mapping_fix_lanes_current.json"
DEFAULT_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_mapping_fix_retry_policy_templates_current.json"
DEFAULT_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_RESCUE_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_REFINEMENT_LANE_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_cathepsin_k_allatom_review_packet_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_REFINEMENT_LANE_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.json"
DEFAULT_PARTNERING_STACK_JSON = "runs/wetlab_partnering_stack_current.json"
DEFAULT_MASTER_HANDOFF_JSON = "runs/wetlab_master_handoff_dashboard_current.json"
DEFAULT_FINAL_SUMMARY_JSON = "runs/wetlab_final_campaign_summary_current.json"
DEFAULT_MASTER_TERMINAL_REVIEW_JSON = "runs/wetlab_master_terminal_review_current.json"
DEFAULT_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON = "runs/selected_allatom_visual_bundle_current.json"
DEFAULT_LIGAND_ADMET_MODULE_JSON = "runs/ligand_admet_module_current.json"
DEFAULT_OUT_MD = "runs/wetlab_current_results_index_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _is_full_partnering_stack_summary(summary: dict[str, Any] | None) -> bool:
    summary = dict(summary or {})
    if not summary:
        return False
    if _text(summary.get("status")) != "wetlab_partnering_stack_ready":
        return False
    marker_complete = _text(summary.get("artifact_kind")) == "wetlab_partnering_stack" and _text(
        summary.get("artifact_completeness")
    ) == "full_partnering_stack"
    required_keys = (
        "portfolio_target_count",
        "wave1_target_count",
        "selected_allatom_target_id",
        "selected_allatom_surface_label",
        "selected_allatom_best_mean_min_distance_A",
        "selected_allatom_best_mean_min_distance_A_source",
        "selected_allatom_wetlab_gate_pass",
        "selected_allatom_final_gate_pass",
    )
    required_fields_present = all(key in summary and summary.get(key) not in {"", None} for key in required_keys)
    return marker_complete and required_fields_present


def _partnering_stack_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(payload)
    return summary if _is_full_partnering_stack_summary(summary) else {}


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _compound_display_name(*values: Any) -> str:
    return _text(*values)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _coerce_boolish(value: Any) -> bool | None:
    if value in {"", None}:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 0:
            return False
        if value == 1:
            return True
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return bool(value)


def _coerce_list(value: Any) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return [dict(value)]
    return []


def _resolve_value_from_specs(
    specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    *,
    default: Any = None,
) -> Any:
    for summary, keys in specs:
        if not summary:
            continue
        for key in keys:
            if key not in summary:
                continue
            value = summary.get(key)
            if value is not None and value != "":
                return value
    return default


def _resolve_gate_snapshot(
    *,
    operator_review_specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    wetlab_gate_specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    final_gate_specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    claim_gate_available_specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    claim_ready_specs: list[tuple[dict[str, Any] | None, tuple[str, ...]]],
    default_ready: bool = False,
) -> dict[str, bool]:
    operator_review_ready = _coerce_boolish(
        _resolve_value_from_specs(operator_review_specs, default=default_ready)
    )
    wetlab_gate_pass = _coerce_boolish(
        _resolve_value_from_specs(
            wetlab_gate_specs,
            default=operator_review_ready if operator_review_ready is not None else default_ready,
        )
    )
    wetlab_final_gate_pass = _coerce_boolish(
        _resolve_value_from_specs(
            final_gate_specs,
            default=wetlab_gate_pass if wetlab_gate_pass is not None else default_ready,
        )
    )
    claim_gate_available = _coerce_boolish(
        _resolve_value_from_specs(claim_gate_available_specs, default=False)
    )
    claim_ready_for_allatom = _coerce_boolish(
        _resolve_value_from_specs(claim_ready_specs, default=False)
    )
    return {
        "packet_ready_for_operator_review": bool(operator_review_ready),
        "wetlab_gate_pass": bool(wetlab_gate_pass),
        "wetlab_final_gate_pass": bool(wetlab_final_gate_pass),
        "claim_gate_available": bool(claim_gate_available),
        "claim_ready_for_allatom": bool(claim_ready_for_allatom),
    }


def _gate_status_tokens(
    snapshot: dict[str, bool],
    *,
    reported: dict[str, bool] | None = None,
) -> tuple[str, str, str]:
    reported = reported or {}
    operator_review = (
        "operator review ready"
        if snapshot.get("packet_ready_for_operator_review", False)
        else "operator review blocked"
        if reported.get("packet_ready_for_operator_review", True)
        else "operator review not reported"
    )
    final_gate = (
        "final gate pass"
        if snapshot.get("wetlab_final_gate_pass", False)
        else "final gate blocked"
        if reported.get("wetlab_final_gate_pass", True)
        else "final gate not reported"
    )
    claim_reported = reported.get("claim_gate_available", True) or reported.get(
        "claim_ready_for_allatom",
        True,
    )
    claim_gate = (
        "claim ready"
        if snapshot.get("claim_ready_for_allatom", False)
        else "claim gate blocked"
        if snapshot.get("claim_gate_available", False)
        else "claim gate unavailable"
        if claim_reported
        else "claim gate not reported"
    )
    return operator_review, final_gate, claim_gate


def _resolve_named_bool_from_specs(
    specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
) -> tuple[bool, bool, str]:
    for source_label, summary, keys in specs:
        if not summary:
            continue
        for key in keys:
            if key not in summary:
                continue
            value = _coerce_boolish(summary.get(key))
            if value is not None:
                return True, bool(value), f"{source_label}.{key}"
    return False, False, ""


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item or "").strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _resolve_named_value_from_specs(
    specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
) -> tuple[bool, Any, str]:
    for source_label, summary, keys in specs:
        if not summary:
            continue
        for key in keys:
            if key not in summary:
                continue
            value = summary.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, (list, tuple, set)) and not list(value):
                continue
            return True, value, f"{source_label}.{key}"
    return False, None, ""


def _selected_review_packet_metric(
    selected_source: dict[str, Any] | None,
    *,
    target_id: str,
    surface_label: str,
    metric_key: str,
) -> tuple[bool, Any, str]:
    if not selected_source or selected_source.get("surface_kind") != "review_packet":
        return False, None, ""
    summary = dict(selected_source.get("summary", {}) or {})
    source_target_id = _text(summary.get("target_id"), selected_source.get("target_id"))
    source_surface_label = _text(
        summary.get("surface_label"),
        selected_source.get("surface_label"),
    )
    if _text(target_id) != source_target_id or _text(surface_label) != source_surface_label:
        return False, None, ""
    if metric_key not in summary or summary.get(metric_key) in {"", None}:
        return False, None, ""
    return True, summary.get(metric_key), f"{source_surface_label}.{metric_key}"


def _clean(value: Any) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip()
    return text.replace("|", "\\|")


def _pid_snapshot(path_like: str) -> dict[str, Any]:
    path = Path(path_like)
    if not path.is_absolute():
        path = ROOT / path
    snapshot = {
        "pid_path": str(path),
        "pid": 0,
        "pid_alive": False,
        "pid_state": "missing",
    }
    if not path.exists():
        return snapshot
    try:
        pid = int(path.read_text(encoding="utf-8").strip() or 0)
    except Exception:
        snapshot["pid_state"] = "invalid"
        return snapshot
    snapshot["pid"] = pid
    if pid <= 0:
        snapshot["pid_state"] = "invalid"
        return snapshot
    try:
        os.kill(pid, 0)
    except OSError:
        snapshot["pid_state"] = "stale"
        return snapshot
    snapshot["pid_alive"] = True
    snapshot["pid_state"] = "alive"
    return snapshot


def _watch_loop_text(snapshot: dict[str, Any]) -> str:
    attached = bool(snapshot.get("pid_alive", False))
    pid_state = str(snapshot.get("pid_state", "")).strip()
    liveness = "attached" if attached else "stale" if pid_state == "stale" else "detached"
    fallback = "compute-attached" if attached else "stale-recovery" if liveness == "stale" else "manual-restart"
    return f"watch loop attached {'yes' if attached else 'no'} | liveness {liveness} | fallback {fallback}"


def _row(
    *,
    group: str,
    surface: str,
    artifact: str,
    status: str,
    key_signal: str,
    one_line_summary: str,
) -> dict[str, Any]:
    return {
        "group": group,
        "surface": surface,
        "artifact": artifact,
        "status": status,
        "key_signal": key_signal,
        "one_line_summary": one_line_summary,
    }


def _group_signal(rows: list[dict[str, Any]]) -> str:
    parts = [str(row.get("key_signal", "")).strip() for row in rows if str(row.get("key_signal", "")).strip()]
    return "; ".join(parts[:2]) if parts else ""


def _primary_queue_rows(primary_queue: dict[str, Any], antitarget_queue: dict[str, Any]) -> list[dict[str, Any]]:
    p = _summary(primary_queue)
    a = _summary(antitarget_queue)
    return [
        _row(
            group="primary/counterscreen queue",
            surface="primary_execution_queue",
            artifact="runs/wetlab_broad_screen_execution_queue_current.md",
            status=_text(p.get("status"), default="missing"),
            key_signal=_joined(
                p.get("first_actionable_target_id"),
                p.get("first_actionable_shard_id"),
                p.get("first_actionable_queue_status"),
            ),
            one_line_summary=_joined(
                p.get("first_actionable_target_id"),
                p.get("first_actionable_shard_id"),
                p.get("first_actionable_queue_status"),
                p.get("next_required_step"),
            ),
        ),
        _row(
            group="primary/counterscreen queue",
            surface="antitarget_execution_queue",
            artifact="runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            status=_text(a.get("status"), default="missing"),
            key_signal=_joined(
                a.get("first_actionable_primary_target_id"),
                a.get("first_actionable_anti_target_id"),
                a.get("first_actionable_shard_id"),
                a.get("first_actionable_queue_status"),
            ),
            one_line_summary=_joined(
                a.get("first_actionable_primary_target_id"),
                a.get("first_actionable_anti_target_id"),
                a.get("first_actionable_shard_id"),
                a.get("first_actionable_queue_status"),
                a.get("next_required_step"),
            ),
        ),
    ]


def _watch_state_rows(primary_watch_state: dict[str, Any], antitarget_watch_state: dict[str, Any]) -> list[dict[str, Any]]:
    p = _summary(primary_watch_state)
    a = _summary(antitarget_watch_state)
    p_loop = _pid_snapshot(DEFAULT_PRIMARY_WATCH_LOOP_PID)
    a_loop = _pid_snapshot(DEFAULT_ANTITARGET_WATCHER_LOOP_PID)
    p_loop_text = _watch_loop_text(p_loop)
    a_loop_text = _watch_loop_text(a_loop)
    return [
        _row(
            group="watch state",
            surface="primary_watch_state",
            artifact="runs/wetlab_broad_screen_primary_watch_state_current.md",
            status=_text(p.get("status"), default="missing"),
            key_signal=_joined(p.get("watcher_decision"), p.get("active_queue_status"), p_loop_text),
            one_line_summary=_joined(p.get("watcher_decision"), p.get("next_required_step"), p_loop_text),
        ),
        _row(
            group="watch state",
            surface="antitarget_watcher_state",
            artifact="runs/wetlab_broad_screen_antitarget_watcher_state_current.md",
            status=_text(a.get("status"), default="missing"),
            key_signal=_joined(a.get("watcher_decision"), a.get("active_queue_status"), a_loop_text),
            one_line_summary=_joined(a.get("watcher_decision"), a.get("next_required_step"), a_loop_text),
        ),
    ]


def _precision_monitor_rows(precision_monitor: dict[str, Any]) -> list[dict[str, Any]]:
    s = _summary(precision_monitor)
    return [
        _row(
            group="precision monitor",
            surface="precision_monitor",
            artifact="runs/wetlab_broad_screen_precision_monitor_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                f"{_safe_float(s.get('completion_pct')):.1f}%",
                f"success {_safe_float(s.get('successful_completion_pct')):.1f}%",
                f"hold {_safe_float(s.get('held_completion_pct')):.1f}%",
                f"focus {_text(s.get('focus_target_id'))} {_text(s.get('focus_shard_id'))}",
            ),
            one_line_summary=_joined(
                f"{_safe_float(s.get('completion_pct')):.1f}% overall",
                f"success {_safe_float(s.get('successful_completion_pct')):.1f}%",
                f"hold {_safe_float(s.get('held_completion_pct')):.1f}%",
                f"focus {_text(s.get('focus_target_id'))} {_text(s.get('focus_shard_id'))}",
            ),
        )
    ]


def _failure_surface_rows(failure_surface: dict[str, Any]) -> list[dict[str, Any]]:
    s = _summary(failure_surface)
    return [
        _row(
            group="failure surface",
            surface="primary_stage6_failure_surface",
            artifact="runs/wetlab_primary_stage6_failure_surface_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                f"{_safe_int(s.get('surface_row_count', s.get('auto_hold_row_count')))} rows",
                f"pending {_safe_int(s.get('watcher_pending_failure_row_count'))}",
                f"stage1 {_safe_int(s.get('stage1_mapping_failed_count'))}",
                f"stage6 {_safe_int(s.get('stage6_failed_count'))}",
            ),
            one_line_summary=_joined(
                f"{_safe_int(s.get('surface_row_count', s.get('auto_hold_row_count')))} failure rows",
                f"{_safe_int(s.get('stage1_mapping_failed_count'))} stage1 mapping failures",
                f"{_safe_int(s.get('stage6_failed_count'))} stage6 failures",
                f"{_safe_int(s.get('watcher_pending_failure_row_count'))} watcher-pending",
                f"{_safe_int(s.get('sparse_top_level_row_count'))} sparse-top backfilled",
            ),
        )
    ]


def _retry_preset_rows(primary_retry: dict[str, Any], antitarget_retry: dict[str, Any]) -> list[dict[str, Any]]:
    p = _summary(primary_retry)
    a = _summary(antitarget_retry)
    return [
        _row(
            group="retry preset surface",
            surface="primary_throughput_bridge",
            artifact="runs/wetlab_broad_screen_throughput_bridge_current.md",
            status=_text(p.get("status"), default="missing"),
            key_signal=_joined(p.get("target_id"), p.get("shard_id"), p.get("preferred_command_kind")),
            one_line_summary=_joined(p.get("target_id"), p.get("shard_id"), p.get("next_required_step")),
        ),
        _row(
            group="retry preset surface",
            surface="antitarget_throughput_bridge",
            artifact="runs/wetlab_broad_screen_antitarget_throughput_bridge_current.md",
            status=_text(a.get("status"), default="missing"),
            key_signal=_joined(a.get("primary_target_id"), a.get("anti_target_id"), a.get("shard_id"), a.get("preferred_command_kind")),
            one_line_summary=_joined(a.get("primary_target_id"), a.get("anti_target_id"), a.get("shard_id"), a.get("next_required_step")),
        ),
    ]


def _hold_guard_rows(hold_guard: dict[str, Any]) -> list[dict[str, Any]]:
    s = _summary(hold_guard)
    return [
        _row(
            group="hold guard surface",
            surface="primary_watch_action",
            artifact="runs/wetlab_broad_screen_primary_watch_action_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("guard_blocked_target_id"),
                f"hold streak { _safe_int(s.get('guard_hold_streak')) }",
                f"limit { _safe_int(s.get('guard_hold_limit')) }",
            ),
            one_line_summary=_joined(
                f"{_text(s.get('guard_blocked_target_id'))} blocked after {_safe_int(s.get('guard_hold_streak'))} consecutive auto-holds",
                f"guard limit {_safe_int(s.get('guard_hold_limit'))}",
            ),
        )
    ]


def _manual_retry_step_from_lane(lane_payload: dict[str, Any] | None) -> str:
    lane = _summary(lane_payload)
    lane_label = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    status = _text(lane.get("status"))
    selectable = bool(lane.get("ready_for_manual_retry", False)) or (
        lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
    )
    if not selectable:
        return ""
    explicit_next_step = _text(lane.get("next_required_step"))
    if explicit_next_step:
        return explicit_next_step
    target_id = _text(lane.get("target_id"))
    shard_id = _text(lane.get("shard_id"))
    selected_kind = _text(lane.get("selected_command_kind"))
    explicit_label = lane_label
    followup_shards = _text(lane.get("followup_shard_ids"))
    if explicit_label == "exploratory_gate4.5_followup" or _text(lane.get("hard_freeze_state")) == "hard_freeze_after_exploratory_success":
        label = "exploratory gate4.5 follow-up runner"
    elif "gate45" in selected_kind:
        label = "exploratory gate4.5 manual retry runner"
    elif "gate55" in selected_kind:
        label = "tuned gate55 manual retry runner"
    else:
        label = "manual retry runner"
    if target_id and shard_id:
        freeze_clause = (
            "keep auto-start hard-frozen."
            if label == "exploratory gate4.5 follow-up runner"
            else "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
        return f"Run the {target_id} {label} for {shard_id}; {freeze_clause}"
    if target_id:
        freeze_clause = (
            "keep auto-start hard-frozen."
            if label == "exploratory gate4.5 follow-up runner"
            else "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
        return f"Run the {target_id} {label}; {freeze_clause}"
    return ""


def _manual_retry_lane_label(lane_payload: dict[str, Any] | None) -> str:
    lane = _summary(lane_payload)
    explicit = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    if explicit:
        return explicit
    if _text(lane.get("hard_freeze_state")) == "hard_freeze_after_exploratory_success":
        return "exploratory_gate4.5_followup"
    selected_kind = _text(lane.get("selected_command_kind"))
    if "gate45" in selected_kind:
        return "exploratory_gate4.5"
    if "gate55" in selected_kind:
        return "tuned_gate55"
    if _text(lane.get("target_id")):
        return "manual_retry"
    return ""


def _lane_shard_display(lane_payload: dict[str, Any] | None) -> str:
    lane = _summary(lane_payload)
    lane_label = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    if lane_label == "exploratory_gate4.5_followup":
        return _text(lane.get("shard_id"), lane.get("followup_shard_ids"))
    return _text(lane.get("shard_id"))


def _lane_matches_selected(
    lane_payload: dict[str, Any] | None,
    *,
    selected_target_id: str,
    selected_shard_id: str,
    selected_command_kind: str,
) -> bool:
    lane = _summary(lane_payload)
    return bool(
        _text(lane.get("target_id")) == _text(selected_target_id)
        and _lane_shard_display(lane_payload) == _text(selected_shard_id)
        and _text(lane.get("selected_command_kind")) == _text(selected_command_kind)
    )


def _select_manual_retry_lane(
    retry_handoff_summary: dict[str, Any],
    *lane_payloads: dict[str, Any] | None,
) -> dict[str, Any]:
    handoff = _summary(retry_handoff_summary)
    focus_target = _text(handoff.get("manual_retry_focus_target_id"), handoff.get("guard_blocked_target_id"))
    candidates: list[dict[str, Any]] = []
    for payload in lane_payloads:
        summary = _summary(payload)
        lane_label = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
        status = _text(summary.get("status"))
        if bool(summary.get("ready_for_manual_retry", False)) or (
            lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
        ) or (
            status.startswith("wetlab_lbdhodh_exploratory_retry_lane_")
            and _text(summary.get("queue_status")) == "running"
            and _text(summary.get("next_required_step"))
        ):
            candidates.append(payload or {})
    selected_lane_label = _text(handoff.get("selected_manual_retry_lane_label"))
    selected_target = _text(handoff.get("selected_manual_retry_target_id"))
    selected_shard = _text(handoff.get("selected_manual_retry_shard_id"))
    selected_kind = _text(handoff.get("selected_manual_retry_selected_command_kind"))
    if selected_lane_label or selected_target or selected_shard or selected_kind:
        for payload in candidates:
            summary = _summary(payload)
            lane_label = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
            if selected_lane_label and lane_label != selected_lane_label:
                continue
            if selected_target and _text(summary.get("target_id")) != selected_target:
                continue
            if selected_shard and _lane_shard_display(payload) != selected_shard:
                continue
            if selected_kind and _text(summary.get("selected_command_kind")) != selected_kind:
                continue
            return payload
    if focus_target:
        for payload in candidates:
            if _text(_summary(payload).get("target_id")) == focus_target:
                return payload
    return candidates[0] if candidates else {}


def _manual_retry_lane_rows(
    retry_handoff_summary: dict[str, Any],
    lbdhodh_exploratory_retry_lane: dict[str, Any],
    stk17b_manual_retry_lane: dict[str, Any],
    stk17b_exploratory_retry_lane: dict[str, Any],
    stk17b_exploratory_followup_lane: dict[str, Any],
    plpro_manual_retry_lane: dict[str, Any],
    mapping_fix_retry_support: dict[str, Any],
    stage1_mapping_fix_lanes: dict[str, Any],
) -> list[dict[str, Any]]:
    handoff = _summary(retry_handoff_summary)
    lbdhodh = _summary(lbdhodh_exploratory_retry_lane)
    stk17b = _summary(stk17b_manual_retry_lane)
    stk17b_exploratory = _summary(stk17b_exploratory_retry_lane)
    stk17b_exploratory_followup = _summary(stk17b_exploratory_followup_lane)
    plpro = _summary(plpro_manual_retry_lane)
    mapping = _summary(mapping_fix_retry_support)
    stage1_mapping = _summary(stage1_mapping_fix_lanes)
    lbdhodh_retry_step = _manual_retry_step_from_lane(lbdhodh_exploratory_retry_lane)
    stk17b_manual_retry_step = _manual_retry_step_from_lane(stk17b_manual_retry_lane)
    stk17b_exploratory_retry_step = _manual_retry_step_from_lane(stk17b_exploratory_retry_lane)
    stk17b_exploratory_followup_step = _manual_retry_step_from_lane(stk17b_exploratory_followup_lane)
    plpro_manual_retry_step = _manual_retry_step_from_lane(plpro_manual_retry_lane)
    handoff_next_required_step = _text(handoff.get("next_required_step"))
    selected_allatom_handoff_step = _text(handoff.get("selected_allatom_next_required_step"))
    if selected_allatom_handoff_step and handoff_next_required_step == selected_allatom_handoff_step:
        handoff_next_required_step = ""
    if "strict_only gate did not pass" in handoff_next_required_step:
        handoff_next_required_step = ""
    selected_lane_payload = _select_manual_retry_lane(
        retry_handoff_summary,
        lbdhodh_exploratory_retry_lane,
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
    )
    selected_lane_summary = _summary(selected_lane_payload)
    selected_target_id = _text(handoff.get("selected_manual_retry_target_id"), selected_lane_summary.get("target_id"))
    selected_shard_id = _text(handoff.get("selected_manual_retry_shard_id"), _lane_shard_display(selected_lane_payload))
    selected_command_kind = _text(
        handoff.get("selected_manual_retry_selected_command_kind"),
        selected_lane_summary.get("selected_command_kind"),
    )
    lane_rows: list[dict[str, Any]] = []
    if lbdhodh:
        lane_rows.append(
            _row(
                group="manual retry lanes",
                surface="lbdhodh_exploratory_retry_lane",
                artifact="runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
                status=_text(lbdhodh.get("status"), default="missing"),
                key_signal=_joined(
                    lbdhodh.get("target_id"),
                    lbdhodh.get("shard_id"),
                    lbdhodh.get("selected_command_kind"),
                    _manual_retry_lane_label(lbdhodh_exploratory_retry_lane),
                    "selected"
                    if _lane_matches_selected(
                        lbdhodh_exploratory_retry_lane,
                        selected_target_id=selected_target_id,
                        selected_shard_id=selected_shard_id,
                        selected_command_kind=selected_command_kind,
                    )
                    else "running"
                    if _text(lbdhodh.get("queue_status")) == "running"
                    else "ready"
                    if bool(lbdhodh.get("ready_for_manual_retry", False))
                    else "blocked",
                ),
                one_line_summary=_joined(
                    lbdhodh.get("target_id"),
                    lbdhodh_retry_step,
                ),
            )
        )
    if stk17b_exploratory_followup:
        lane_rows.append(
            _row(
                group="manual retry lanes",
                surface="stk17b_exploratory_followup_lane",
                artifact="runs/wetlab_stk17b_exploratory_followup_lane_current.md",
                status=_text(stk17b_exploratory_followup.get("status"), default="missing"),
                key_signal=_joined(
                    stk17b_exploratory_followup.get("target_id"),
                    stk17b_exploratory_followup.get("shard_id"),
                    stk17b_exploratory_followup.get("selected_command_kind"),
                    _manual_retry_lane_label(stk17b_exploratory_followup_lane),
                    "selected"
                    if _lane_matches_selected(
                        stk17b_exploratory_followup_lane,
                        selected_target_id=selected_target_id,
                        selected_shard_id=selected_shard_id,
                        selected_command_kind=selected_command_kind,
                    )
                    else "ready" if bool(stk17b_exploratory_followup.get("ready_for_manual_retry", False)) else "blocked",
                ),
                one_line_summary=_joined(
                    stk17b_exploratory_followup.get("target_id"),
                    stk17b_exploratory_followup_step,
                    _text(stk17b_exploratory_followup.get("freeze_note")),
                ),
            )
        )
    if stk17b:
        lane_rows.append(
            _row(
                group="manual retry lanes",
                surface="stk17b_manual_retry_lane",
                artifact="runs/wetlab_stk17b_manual_retry_lane_current.md",
                status=_text(stk17b.get("status"), default="missing"),
                key_signal=_joined(
                    stk17b.get("target_id"),
                    stk17b.get("shard_id"),
                    stk17b.get("selected_command_kind"),
                    _manual_retry_lane_label(stk17b_manual_retry_lane),
                    "selected"
                    if _lane_matches_selected(
                        stk17b_manual_retry_lane,
                        selected_target_id=selected_target_id,
                        selected_shard_id=selected_shard_id,
                        selected_command_kind=selected_command_kind,
                    )
                    else "ready" if bool(stk17b.get("ready_for_manual_retry", False)) else "blocked",
                ),
                one_line_summary=_joined(
                    stk17b.get("target_id"),
                    stk17b_manual_retry_step,
                ),
            )
        )
    if stk17b_exploratory:
        lane_rows.append(
            _row(
                group="manual retry lanes",
                surface="stk17b_exploratory_retry_lane",
                artifact="runs/wetlab_stk17b_exploratory_retry_lane_current.md",
                status=_text(stk17b_exploratory.get("status"), default="missing"),
                key_signal=_joined(
                    stk17b_exploratory.get("target_id"),
                    stk17b_exploratory.get("shard_id"),
                    stk17b_exploratory.get("selected_command_kind"),
                    _manual_retry_lane_label(stk17b_exploratory_retry_lane),
                    "selected"
                    if _lane_matches_selected(
                        stk17b_exploratory_retry_lane,
                        selected_target_id=selected_target_id,
                        selected_shard_id=selected_shard_id,
                        selected_command_kind=selected_command_kind,
                    )
                    else "ready" if bool(stk17b_exploratory.get("ready_for_manual_retry", False)) else "blocked",
                ),
                one_line_summary=_joined(
                    stk17b_exploratory.get("target_id"),
                    stk17b_exploratory_retry_step,
                ),
            )
        )
    if plpro:
        lane_rows.append(
            _row(
                group="manual retry lanes",
                surface="plpro_manual_retry_lane",
                artifact="runs/wetlab_plpro_manual_retry_lane_current.md",
                status=_text(plpro.get("status"), default="missing"),
                key_signal=_joined(
                    plpro.get("target_id"),
                    plpro.get("shard_id"),
                    plpro.get("selected_command_kind"),
                    _manual_retry_lane_label(plpro_manual_retry_lane),
                    "selected"
                    if _lane_matches_selected(
                        plpro_manual_retry_lane,
                        selected_target_id=selected_target_id,
                        selected_shard_id=selected_shard_id,
                        selected_command_kind=selected_command_kind,
                    )
                    else "ready" if bool(plpro.get("ready_for_manual_retry", False)) else "blocked",
                ),
                one_line_summary=_joined(
                    plpro.get("target_id"),
                    plpro_manual_retry_step,
                ),
            )
        )
    lane_rows.sort(
        key=lambda row: (
            0 if "selected" in str(row.get("key_signal", "")) else 1,
            0 if str(row.get("surface", "")) == "stk17b_exploratory_followup_lane" else 1,
            0 if str(row.get("surface", "")) == "stk17b_exploratory_retry_lane" else 1,
            str(row.get("surface", "")),
        )
    )
    return [
        _row(
            group="manual retry lanes",
            surface="retry_handoff_summary",
            artifact="runs/wetlab_retry_handoff_summary_current.md",
            status=_text(handoff.get("status"), default="missing"),
            key_signal=_joined(
                handoff.get("manual_retry_focus_target_id"),
                handoff.get("manual_retry_focus_decision"),
                handoff.get("selected_manual_retry_lane_label"),
            ),
            one_line_summary=_joined(
                handoff.get("manual_retry_priority_targets"),
                handoff.get("current_results_next_required_step"),
                handoff_next_required_step,
            ),
        ),
        *lane_rows,
        _row(
            group="manual retry lanes",
            surface="mapping_fix_retry_support",
            artifact="runs/wetlab_mapping_fix_retry_support_current.md",
            status=_text(mapping.get("status"), default="missing"),
            key_signal=_joined(
                mapping.get("ready_targets"),
                f"{_safe_int(mapping.get('ready_target_count'))} ready",
            ),
            one_line_summary=_joined(
                mapping.get("ready_targets"),
                mapping.get("next_required_step"),
            ),
        ),
        _row(
            group="manual retry lanes",
            surface="stage1_mapping_fix_lanes",
            artifact="runs/wetlab_stage1_mapping_fix_lanes_current.md",
            status=_text(stage1_mapping.get("status"), default="missing"),
            key_signal=_joined(
                stage1_mapping.get("ready_targets"),
                f"{_safe_int(stage1_mapping.get('ready_target_count'))} ready",
            ),
            one_line_summary=_joined(
                stage1_mapping.get("ready_targets"),
                stage1_mapping.get("next_required_step"),
            ),
        ),
    ]


def _lbdhodh_gate51_validation_review_rows(validation_review: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(validation_review)
    if not s:
        return []
    return [
        _row(
            group="validation review surfaces",
            surface="lbdhodh_gate51_validation_review_surface",
            artifact="runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("decision"),
                f"{_safe_int(s.get('gate51_validation_success_count'))} validated",
                f"{_safe_int(s.get('default_lane_hold_count'))} held",
            ),
            one_line_summary=_joined(
                s.get("decision"),
                s.get("next_required_step"),
            ),
        )
    ]


def _krs1_branch_review_rows(branch_review: dict[str, Any] | None, *, selected: bool = False) -> list[dict[str, Any]]:
    s = _summary(branch_review)
    if not s or _text(s.get("status")) != "wetlab_tcruzi_krs1_branch_review_surface_ready":
        return []
    return [
        _row(
            group="branch review surfaces",
            surface="krs1_branch_review_surface",
            artifact="runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("branch_label"),
                f"{_safe_float(s.get('stage6_tuning_recommended_threshold_A'), 0.0):.2f}A",
                s.get("exploratory_retry_lane_label"),
                "selected" if selected else "ready",
            ),
            one_line_summary=_joined(
                s.get("next_required_step"),
                s.get("successor_target"),
            ),
        )
    ]


def _dpre1_branch_review_rows(branch_review: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(branch_review)
    if not s:
        return []
    return [
        _row(
            group="branch review surfaces",
            surface="dpre1_branch_review_surface",
            artifact="runs/wetlab_dpre1_branch_review_surface_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("source_priority"),
                s.get("branch_label"),
                f"{_safe_float(s.get('stage6_tuning_recommended_threshold_A'), 0.0):.2f}A",
            ),
            one_line_summary=_joined(
                s.get("next_required_step"),
                s.get("exploratory_retry_next_required_step"),
            ),
        )
    ]


def _tcruzi_pde_rescue_review_rows(review_surface: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(review_surface)
    if not s:
        return []
    return [
        _row(
            group="rescue review surfaces",
            surface="tcruzi_pde_rescue_review_surface",
            artifact="runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("decision"),
                f"{_safe_int(s.get('under_2p5_candidate_count'))} <=2.5A",
                f"{_safe_int(s.get('promoted_candidate_count'))} <=3.0A",
            ),
            one_line_summary=_joined(
                s.get("decision"),
                s.get("next_required_step"),
            ),
        )
    ]


def _tcruzi_pde_promoted_top4_review_packet_rows(review_packet: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(review_packet)
    if not s:
        return []
    gate_snapshot = _resolve_gate_snapshot(
        operator_review_specs=[(s, ("packet_ready_for_operator_review", "packet_ready"))],
        wetlab_gate_specs=[(s, ("wetlab_gate_pass", "packet_ready"))],
        final_gate_specs=[(s, ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"))],
        claim_gate_available_specs=[(s, ("claim_gate_available",))],
        claim_ready_specs=[(s, ("claim_ready_for_allatom",))],
        default_ready=_text(s.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
    )
    operator_review_text, final_gate_text, claim_gate_text = _gate_status_tokens(gate_snapshot)
    return [
        _row(
            group="rescue review surfaces",
            surface="tcruzi_pde_promoted_top4_review_packet",
            artifact="runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("packet_scope"),
                operator_review_text,
                final_gate_text,
            ),
            one_line_summary=_joined(
                _compound_display_name(
                    s.get("best_compound_name_human_readable"),
                    s.get("best_compound_name"),
                    s.get("best_ligand_id"),
                ),
                f"{_safe_float(s.get('best_mean_min_distance_A')):.3f}A" if _safe_float(s.get("best_mean_min_distance_A")) else "",
                claim_gate_text,
                s.get("next_required_step"),
            ),
        )
    ]


def _tcruzi_pde_rescue_only_branch_summary_rows(branch_summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(branch_summary)
    if not s:
        return []
    gate_snapshot = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                s,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            )
        ],
        wetlab_gate_specs=[
            (
                s,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            )
        ],
        final_gate_specs=[
            (
                s,
                (
                    "review_packet_final_gate_pass",
                    "wetlab_final_gate_pass",
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            )
        ],
        claim_gate_available_specs=[(s, ("review_packet_claim_gate_available", "claim_gate_available"))],
        claim_ready_specs=[(s, ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"))],
        default_ready=bool(
            _text(s.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
            and bool(s.get("promoted_top4_packet_ready", False))
        ),
    )
    operator_review_text, final_gate_text, claim_gate_text = _gate_status_tokens(gate_snapshot)
    return [
        _row(
            group="rescue review surfaces",
            surface="tcruzi_pde_rescue_only_branch_summary",
            artifact="runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                s.get("branch_state"),
                operator_review_text,
                final_gate_text,
            ),
            one_line_summary=_joined(
                _compound_display_name(
                    s.get("best_compound_name_human_readable"),
                    s.get("best_compound_name"),
                    s.get("best_ligand_id"),
                ),
                f"{_safe_int(s.get('promoted_candidate_count'))} promoted",
                claim_gate_text,
                s.get("next_required_step"),
            ),
        )
    ]


def _kinase_retry_template_rows(kinase_retry_policy_templates: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(kinase_retry_policy_templates)
    if not s:
        return []
    return [
        _row(
            group="kinase retry templates",
            surface="kinase_retry_policy_templates",
            artifact="runs/wetlab_kinase_retry_policy_templates_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("focus_target_id"),
                s.get("focus_template_label"),
                s.get("focus_selected_command_kind"),
                f"{_safe_int(s.get('empirical_validated_target_count'))} empirical",
            ),
            one_line_summary=_joined(
                f"{_safe_int(s.get('template_target_count'))} templates",
                f"{_safe_int(s.get('gate45_only_target_count'))} gate4.5-only",
                f"{_safe_int(s.get('guarded_gate55_candidate_target_count'))} gate55 candidates",
                s.get("next_required_step"),
            ),
        ),
    ]


def _target_retry_template_rows(target_retry_policy_templates: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(target_retry_policy_templates)
    if not s:
        return []
    return [
        _row(
            group="target retry templates",
            surface="target_retry_policy_templates",
            artifact="runs/wetlab_target_retry_policy_templates_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("focus_target_id"),
                s.get("focus_template_label"),
                s.get("focus_selected_command_kind"),
                f"{_safe_int(s.get('template_target_count'))} templates",
            ),
            one_line_summary=_joined(
                f"{_safe_int(s.get('empirical_validated_target_count'))} empirical",
                f"{_safe_int(s.get('non_kinase_template_target_count'))} non-kinase",
                s.get("next_required_step"),
            ),
        ),
    ]


def _stage6_retry_template_rows(target_retry_policy_templates: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(target_retry_policy_templates)
    rows = [dict(row) for row in (target_retry_policy_templates or {}).get("rows", []) or []]
    stage6_rows = [
        row
        for row in rows
        if _text(row.get("row_kind")) == "target_retry_policy_template"
        and _text(row.get("template_scope")) == "guarded_stage6_tuning_candidate"
    ]
    if not s or not stage6_rows:
        return []

    gate45_rows = [row for row in stage6_rows if _text(row.get("selected_command_kind")).endswith("gate45")]
    gate51_rows = [row for row in stage6_rows if _text(row.get("selected_command_kind")).endswith("gate51")]
    focus_row = next(
        (row for row in stage6_rows if _text(row.get("target_id")) == "Dengue NS2B-NS3 protease"),
        next((row for row in stage6_rows if _text(row.get("target_id")) == "Cathepsin K"), stage6_rows[0]),
    )
    ready_targets = "; ".join(_text(row.get("target_id")) for row in stage6_rows if _text(row.get("target_id")))
    gate45_targets = "; ".join(_text(row.get("target_id")) for row in gate45_rows if _text(row.get("target_id")))
    gate51_targets = "; ".join(_text(row.get("target_id")) for row in gate51_rows if _text(row.get("target_id")))
    return [
        _row(
            group="stage6 retry templates",
            surface="stage6_retry_policy_templates",
            artifact="runs/wetlab_target_retry_policy_templates_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                ready_targets,
                f"gate4.5 {len(gate45_rows)}",
                f"gate5.1 {len(gate51_rows)}",
                _text(focus_row.get("selected_command_kind")),
            ),
            one_line_summary=_joined(
                _text(focus_row.get("next_required_step")),
                f"gate4.5 targets {_text(gate45_targets) or '-'}",
                f"gate5.1 targets {_text(gate51_targets) or '-'}",
            ),
        )
    ]


def _dengue_stage6_rows(
    primary_queue: dict[str, Any] | None,
    dengue_stage6_tuning_surface: dict[str, Any] | None,
    dengue_exploratory_retry_lane: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    queue = _summary(primary_queue)
    tuning = _summary(dengue_stage6_tuning_surface)
    lane = _summary(dengue_exploratory_retry_lane)
    tuning_ready = _text(tuning.get("status")) == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
    lane_ready = _text(lane.get("status")) == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
    if not tuning_ready and not lane_ready:
        return []
    queue_target_id = _text(queue.get("first_actionable_target_id"))
    queue_shard_id = _text(queue.get("first_actionable_shard_id"))
    queue_next_required_step = _text(queue.get("next_required_step"))
    queue_status = _text(queue.get("first_actionable_queue_status"))
    queue_priority = queue_target_id == "Dengue NS2B-NS3 protease" and bool(queue_shard_id)
    target_id = _text(
        queue_target_id if queue_priority else "",
        lane.get("target_id"),
        tuning.get("target_id"),
        "Dengue NS2B-NS3 protease",
    )
    threshold = _safe_float(tuning.get("recommended_observed_threshold_A"), 0.0)
    command_kind = _text(lane.get("selected_command_kind"), tuning.get("immediately_runnable_command_kind"))
    lane_label = _text(lane.get("lane_label"))
    shard_id = _text(queue_shard_id if queue_priority else "", lane.get("shard_id"), tuning.get("next_retry_shard_id"))
    next_required_step = _text(
        queue_next_required_step if queue_priority else "",
        lane.get("next_required_step"),
        tuning.get("next_required_step"),
    )
    source_priority = "execution_queue" if queue_priority else "exploratory_lane" if lane_ready else "tuning_surface"
    return [
        _row(
            group="dengue stage6 retry family",
            surface="dengue_stage6_retry",
            artifact=_text(
                "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md"
                if lane_ready
                else "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md"
            ),
            status=_text(queue_status if queue_priority else "", lane.get("status"), tuning.get("status"), default="missing"),
            key_signal=_joined(
                target_id,
                f"{threshold:.2f}A" if threshold else "",
                command_kind,
                lane_label,
                shard_id,
                source_priority,
            ),
            one_line_summary=_joined(
                target_id,
                shard_id,
                next_required_step,
            ),
        )
    ]


def _mapping_fix_retry_template_rows(mapping_fix_retry_policy_templates: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(mapping_fix_retry_policy_templates)
    if not s:
        return []
    return [
        _row(
            group="mapping-fix retry templates",
            surface="mapping_fix_retry_policy_templates",
            artifact="runs/wetlab_mapping_fix_retry_policy_templates_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("focus_target_id"),
                s.get("focus_template_label"),
                s.get("focus_selected_command_kind"),
                f"ready {_safe_int(s.get('ready_target_count'))}/{_safe_int(s.get('template_target_count'))}",
            ),
            one_line_summary=_joined(
                s.get("ready_targets"),
                s.get("next_required_step"),
            ),
        ),
    ]


def _hard_target_rescue_lane_rows(hard_target_rescue_lane: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(hard_target_rescue_lane)
    if not s:
        return []
    target_id = _text(s.get("target_id"), s.get("focus_target_id"))
    shard_id = _text(s.get("shard_id"), s.get("focus_shard_id"))
    stage1_ok = bool(s.get("stage1_ok", s.get("stage1_passed", False)))
    stage6_fail = bool(s.get("stage6_fail", s.get("stage6_failed", False)))
    auto_hold_streak = _safe_int(s.get("auto_hold_streak", s.get("hold_streak", 0)), 0)
    rescue_eligible = bool(s.get("rescue_eligible", stage1_ok and stage6_fail and auto_hold_streak > 0))
    return [
        _row(
            group="hard-target rescue lane",
            surface="hard_target_rescue_lane",
            artifact="runs/wetlab_hard_target_rescue_lane_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                target_id,
                shard_id,
                s.get("selected_command_kind"),
                "stage1_ok" if stage1_ok else "stage1_bad",
                "stage6_fail" if stage6_fail else "stage6_ok",
            ),
            one_line_summary=_joined(
                f"auto-hold streak {_safe_int(auto_hold_streak)}",
                "rescue eligible" if rescue_eligible else "rescue blocked",
                s.get("next_required_step"),
            ),
        ),
    ]


def _rescue_anchor_artifacts_rows(rescue_anchor_artifacts: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(rescue_anchor_artifacts)
    if not s:
        return []
    return [
        _row(
            group="rescue anchor artifacts",
            surface="rescue_anchor_artifacts",
            artifact="runs/wetlab_rescue_anchor_artifacts_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                f"{_safe_int(s.get('anchor_artifact_count'))} anchors",
                _text(s.get("pocket_anchor_artifact"), s.get("native_anchor_artifact")),
            ),
            one_line_summary=_joined(
                "rescue only" if bool(s.get("rescue_only", False)) else "shared",
                s.get("next_required_step"),
            ),
        ),
    ]


def _rescue_three_bead_candidates_rows(rescue_three_bead_candidates: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(rescue_three_bead_candidates)
    if not s:
        return []
    return [
        _row(
            group="3-bead rescue candidates",
            surface="rescue_three_bead_candidates",
            artifact="runs/wetlab_rescue_three_bead_candidates_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                s.get("target_id"),
                f"top-N {_safe_int(s.get('top_n'))}",
                f"{_safe_int(s.get('candidate_count'))} candidates",
                _text(s.get("selected_command_kind")),
            ),
            one_line_summary=_joined(
                f"{_safe_float(s.get('selected_threshold_A'), 0.0):.2f}A",
                s.get("next_required_step"),
            ),
        ),
    ]


def _ligand_admet_module_rows(ligand_admet_module: dict[str, Any] | None) -> list[dict[str, Any]]:
    s = _summary(ligand_admet_module)
    if not s:
        return []
    return [
        _row(
            group="admet/selectivity module",
            surface="ligand_admet_module",
            artifact="runs/ligand_admet_module_current.md",
            status=_text(s.get("status"), default="missing"),
            key_signal=_joined(
                f"{_safe_int(s.get('target_count'))} targets",
                f"{_safe_int(s.get('compound_count'))} compounds",
                f"{_safe_int(s.get('green_count'))}g/{_safe_int(s.get('yellow_count'))}y/{_safe_int(s.get('red_count'))}r",
            ),
            one_line_summary=_joined(
                s.get("module_scope"),
                s.get("next_required_step"),
            ),
        ),
    ]


def _compact_allatom_state(status: Any, *, has_next_required_step: bool = False) -> str:
    text = _text(status).lower()
    if "running" in text:
        return "running"
    if "ready" in text:
        return "ready"
    if "review" in text:
        return "review"
    if "hold" in text or "blocked" in text or "pause" in text:
        return "held"
    if "complete" in text or "validated" in text:
        return "complete"
    if has_next_required_step:
        return "ready"
    return "present"


def _pose_validation_context_from_summary(
    summary: dict[str, Any] | None,
    *,
    source_label: str = "",
) -> dict[str, Any]:
    fields = build_pose_validation_fields_from_summary(dict(summary or {}))
    return {
        "reported": bool(fields.get("pose_validation_reported", False)),
        "version": _text(fields.get("pose_validation_version")),
        "source": _text(source_label),
        "focus_status": _text(fields.get("pose_validation_status")),
        "focus_soft_status": _text(fields.get("pose_validation_soft_status")),
        "focus_score": fields.get("pose_validation_score"),
        "focus_pass": bool(fields.get("pose_validation_pass", False)),
        "focus_pose_preservation_rmsd_A": fields.get("pose_validation_pose_preservation_rmsd_A"),
        "focus_backmapping_consistency_score": fields.get(
            "pose_validation_backmapping_consistency_score"
        ),
        "focus_thresholds": dict(fields.get("pose_validation_thresholds", {}) or {}),
        "focus_failed_checks": list(fields.get("pose_validation_failed_checks", []) or []),
        "focus_missing_checks": list(fields.get("pose_validation_missing_checks", []) or []),
        "focus_passed_checks": list(fields.get("pose_validation_passed_checks", []) or []),
        "focus_action_codes": list(fields.get("pose_validation_action_codes", []) or []),
        "focus_blocker_codes": list(fields.get("pose_validation_blocker_codes", []) or []),
        "focus_reason": _text(fields.get("pose_validation_reason")),
    }


def _allatom_surface_sources(
    tcruzi_pde_allatom_rescue_lane: dict[str, Any] | None,
    tcruzi_pde_allatom_review_packet: dict[str, Any] | None,
    cathepsin_k_allatom_refinement_lane: dict[str, Any] | None,
    cathepsin_k_allatom_review_packet: dict[str, Any] | None,
    sarscov2_mpro_allatom_refinement_lane: dict[str, Any] | None,
    sarscov2_mpro_allatom_review_packet: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    specs = (
        {
            "payload": tcruzi_pde_allatom_rescue_lane,
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_rescue_lane",
            "line_label": "all-atom rescue lane",
            "artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "surface_kind": "lane",
            "surface_order": 0,
        },
        {
            "payload": tcruzi_pde_allatom_review_packet,
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_review_packet",
            "line_label": "all-atom review packet",
            "artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
            "surface_kind": "review_packet",
            "surface_order": 1,
        },
        {
            "payload": cathepsin_k_allatom_refinement_lane,
            "target_id": "Cathepsin K",
            "surface_label": "cathepsin_k_allatom_refinement_lane",
            "line_label": "all-atom refinement lane",
            "artifact": "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.md",
            "surface_kind": "lane",
            "surface_order": 2,
        },
        {
            "payload": cathepsin_k_allatom_review_packet,
            "target_id": "Cathepsin K",
            "surface_label": "cathepsin_k_allatom_review_packet",
            "line_label": "all-atom review packet",
            "artifact": "runs/wetlab_cathepsin_k_allatom_review_packet_current.md",
            "surface_kind": "review_packet",
            "surface_order": 3,
        },
        {
            "payload": sarscov2_mpro_allatom_refinement_lane,
            "target_id": "SARS-CoV-2 Mpro",
            "surface_label": "sarscov2_mpro_allatom_refinement_lane",
            "line_label": "all-atom refinement lane",
            "artifact": "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.md",
            "surface_kind": "lane",
            "surface_order": 4,
        },
        {
            "payload": sarscov2_mpro_allatom_review_packet,
            "target_id": "SARS-CoV-2 Mpro",
            "surface_label": "sarscov2_mpro_allatom_review_packet",
            "line_label": "all-atom review packet",
            "artifact": "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.md",
            "surface_kind": "review_packet",
            "surface_order": 5,
        },
    )
    sources: list[dict[str, Any]] = []
    for spec in specs:
        summary = _summary(spec["payload"])
        if not summary:
            continue
        target_id = _text(summary.get("target_id"), spec["target_id"])
        sources.append(
            {
                **spec,
                "summary": summary,
                "target_id": target_id,
            }
        )
    return sources


def _allatom_family_members(
    tcruzi_pde_allatom_rescue_lane: dict[str, Any] | None,
    tcruzi_pde_allatom_review_packet: dict[str, Any] | None,
    cathepsin_k_allatom_refinement_lane: dict[str, Any] | None,
    cathepsin_k_allatom_review_packet: dict[str, Any] | None,
    sarscov2_mpro_allatom_refinement_lane: dict[str, Any] | None,
    sarscov2_mpro_allatom_review_packet: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for source in _allatom_surface_sources(
        tcruzi_pde_allatom_rescue_lane,
        tcruzi_pde_allatom_review_packet,
        cathepsin_k_allatom_refinement_lane,
        cathepsin_k_allatom_review_packet,
        sarscov2_mpro_allatom_refinement_lane,
        sarscov2_mpro_allatom_review_packet,
    ):
        summary = source["summary"]
        pose_validation = _pose_validation_context_from_summary(
            summary,
            source_label=source["surface_label"],
        )
        next_required_step = _text(summary.get("next_required_step"))
        state = _compact_allatom_state(summary.get("status"), has_next_required_step=bool(next_required_step))
        commercial_actions = _normalize_string_list(
            summary.get("commercial_primary_upgrade_actions_v1", summary.get("commercial_upgrade_actions_v1", []))
        )
        commercial_reported = bool(
            _text(
                summary.get("commercial_schema_version"),
                summary.get("commercial_risk_bucket_v1"),
                summary.get("commercial_decision_class_v1"),
            )
            or (
                summary.get("commercial_overall_score_v1") is not None
                and summary.get("commercial_overall_score_v1") != ""
            )
            or commercial_actions
        )
        commercial_actions_v2 = _normalize_string_list(
            summary.get("commercial_primary_upgrade_actions_v2", summary.get("commercial_upgrade_actions_v2", []))
        )
        commercial_reported_v2 = bool(
            _text(
                summary.get("commercial_schema_version_v2"),
                summary.get("commercial_risk_bucket_v2"),
                summary.get("commercial_decision_class_v2"),
                summary.get("commercial_human_summary_v2"),
            )
            or (
                summary.get("commercial_overall_score_v2") is not None
                and summary.get("commercial_overall_score_v2") != ""
            )
            or (
                summary.get("commercial_soft_score_v2") is not None
                and summary.get("commercial_soft_score_v2") != ""
            )
            or (
                summary.get("commercial_confidence_score_v2") is not None
                and summary.get("commercial_confidence_score_v2") != ""
            )
            or commercial_actions_v2
        )
        members.append(
            {
                "target_id": source["target_id"],
                "surface_label": source["surface_label"],
                "surface_kind": source["surface_kind"],
                "status": _text(summary.get("status"), default="present"),
                "state": state,
                "artifact": source["artifact"],
                "status_line": f"{source['target_id']} {source['line_label']} {state}".strip(),
                "next_required_step": next_required_step,
                "surface_order": source["surface_order"],
                "commercial_reported_v1": commercial_reported,
                "commercial_schema_version": _text(summary.get("commercial_schema_version")),
                "commercial_hard_gate_pass_v1": bool(
                    _coerce_boolish(summary.get("commercial_hard_gate_pass_v1"))
                ),
                "commercial_overall_score_v1": _safe_float(summary.get("commercial_overall_score_v1"), 0.0),
                "commercial_risk_bucket_v1": _text(summary.get("commercial_risk_bucket_v1")),
                "commercial_decision_class_v1": _text(summary.get("commercial_decision_class_v1")),
                "commercial_primary_upgrade_actions_v1": commercial_actions,
                "commercial_primary_upgrade_actions_text_v1": " | ".join(commercial_actions),
                "commercial_reported_v2": commercial_reported_v2,
                "commercial_schema_version_v2": _text(summary.get("commercial_schema_version_v2")),
                "commercial_hard_gate_pass_v2": bool(
                    _coerce_boolish(summary.get("commercial_hard_gate_pass_v2"))
                ),
                "commercial_soft_score_v2": _safe_float(summary.get("commercial_soft_score_v2"), 0.0),
                "commercial_confidence_score_v2": _safe_float(
                    summary.get("commercial_confidence_score_v2"),
                    0.0,
                ),
                "commercial_overall_score_v2": _safe_float(summary.get("commercial_overall_score_v2"), 0.0),
                "commercial_risk_bucket_v2": _text(summary.get("commercial_risk_bucket_v2")),
                "commercial_decision_class_v2": _text(summary.get("commercial_decision_class_v2")),
                "commercial_primary_upgrade_actions_v2": commercial_actions_v2,
                "commercial_primary_upgrade_actions_text_v2": " | ".join(commercial_actions_v2),
                "commercial_human_summary_v2": _text(summary.get("commercial_human_summary_v2")),
                "translation_gate_version": _text(summary.get("translation_gate_version")),
                "translation_gate_focus_status": _text(summary.get("translation_gate_focus_status")),
                "translation_gate_focus_score": _safe_float(
                    summary.get("translation_gate_focus_score"),
                    0.0,
                ),
                "translation_gate_focus_reason": _text(summary.get("translation_gate_focus_reason")),
                "stronger_physics_shortlist_version": _text(
                    summary.get("stronger_physics_shortlist_version")
                ),
                "focus_shortlist_tier": _text(summary.get("focus_shortlist_tier")),
                "recommended_next_expensive_lane": _text(
                    summary.get("recommended_next_expensive_lane")
                ),
                "recommended_next_expensive_lane_reason": _text(
                    summary.get("recommended_next_expensive_lane_reason")
                ),
                "pose_validation_reported": bool(pose_validation.get("reported", False)),
                "pose_validation_version": _text(pose_validation.get("version")),
                "pose_validation_source": _text(pose_validation.get("source")),
                "pose_validation_focus_status": _text(pose_validation.get("focus_status")),
                "pose_validation_focus_soft_status": _text(
                    pose_validation.get("focus_soft_status")
                ),
                "pose_validation_focus_score": (
                    _safe_float(pose_validation.get("focus_score"), 0.0)
                    if pose_validation.get("focus_score") not in {"", None}
                    else 0.0
                ),
                "pose_validation_focus_pass": bool(pose_validation.get("focus_pass", False)),
                "pose_validation_focus_pose_preservation_rmsd_A": pose_validation.get(
                    "focus_pose_preservation_rmsd_A"
                ),
                "pose_validation_focus_backmapping_consistency_score": pose_validation.get(
                    "focus_backmapping_consistency_score"
                ),
                "pose_validation_focus_thresholds": dict(
                    pose_validation.get("focus_thresholds", {}) or {}
                ),
                "pose_validation_focus_failed_checks": list(
                    pose_validation.get("focus_failed_checks", []) or []
                ),
                "pose_validation_focus_missing_checks": list(
                    pose_validation.get("focus_missing_checks", []) or []
                ),
                "pose_validation_focus_passed_checks": list(
                    pose_validation.get("focus_passed_checks", []) or []
                ),
                "pose_validation_focus_action_codes": list(
                    pose_validation.get("focus_action_codes", []) or []
                ),
                "pose_validation_focus_blocker_codes": list(
                    pose_validation.get("focus_blocker_codes", []) or []
                ),
                "pose_validation_focus_reason": _text(pose_validation.get("focus_reason")),
            }
        )
    return members


def _allatom_family_rows(
    tcruzi_pde_allatom_rescue_lane: dict[str, Any] | None,
    tcruzi_pde_allatom_review_packet: dict[str, Any] | None,
    cathepsin_k_allatom_refinement_lane: dict[str, Any] | None,
    cathepsin_k_allatom_review_packet: dict[str, Any] | None,
    sarscov2_mpro_allatom_refinement_lane: dict[str, Any] | None,
    sarscov2_mpro_allatom_review_packet: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for member in _allatom_family_members(
        tcruzi_pde_allatom_rescue_lane,
        tcruzi_pde_allatom_review_packet,
        cathepsin_k_allatom_refinement_lane,
        cathepsin_k_allatom_review_packet,
        sarscov2_mpro_allatom_refinement_lane,
        sarscov2_mpro_allatom_review_packet,
    ):
        rows.append(
            _row(
                group="all-atom refinement/rescue family",
                surface=member["surface_label"],
                artifact=member["artifact"],
                status=member["status"],
                key_signal=_joined(
                    member["target_id"],
                    member["surface_kind"],
                    member["state"],
                    (
                        f"commercial {_safe_float(member.get('commercial_overall_score_v1')):.1f}"
                        if bool(member.get("commercial_reported_v1", False))
                        else ""
                    ),
                    _text(member.get("commercial_risk_bucket_v1")),
                    _text(member.get("commercial_decision_class_v1")),
                    _text(member.get("pose_validation_focus_status")),
                ),
                one_line_summary=_joined(
                    member["status_line"],
                    (
                        f"commercial {_safe_float(member.get('commercial_overall_score_v1')):.1f}"
                        if bool(member.get("commercial_reported_v1", False))
                        else ""
                    ),
                    _text(member.get("commercial_risk_bucket_v1")),
                    _text(member.get("commercial_decision_class_v1")),
                    _text(member.get("pose_validation_focus_status")),
                    _text(member.get("commercial_primary_upgrade_actions_text_v1")),
                    member["next_required_step"],
                ),
            )
        )
    return rows


def _allatom_family_summary(
    tcruzi_pde_allatom_rescue_lane: dict[str, Any] | None,
    tcruzi_pde_allatom_review_packet: dict[str, Any] | None,
    cathepsin_k_allatom_refinement_lane: dict[str, Any] | None,
    cathepsin_k_allatom_review_packet: dict[str, Any] | None,
    sarscov2_mpro_allatom_refinement_lane: dict[str, Any] | None,
    sarscov2_mpro_allatom_review_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    members = _allatom_family_members(
        tcruzi_pde_allatom_rescue_lane,
        tcruzi_pde_allatom_review_packet,
        cathepsin_k_allatom_refinement_lane,
        cathepsin_k_allatom_review_packet,
        sarscov2_mpro_allatom_refinement_lane,
        sarscov2_mpro_allatom_review_packet,
    )
    if not members:
        return {
            "ready": False,
            "target_count": 0,
            "surface_count": 0,
            "focus_target_id": "",
            "focus_surface_label": "",
            "focus_status_line": "",
            "focus_commercial_reported_v1": False,
            "focus_commercial_schema_version": "",
            "focus_commercial_hard_gate_pass_v1": False,
            "focus_commercial_overall_score_v1": 0.0,
            "focus_commercial_risk_bucket_v1": "",
            "focus_commercial_decision_class_v1": "",
            "focus_commercial_primary_upgrade_actions_v1": [],
            "focus_commercial_primary_upgrade_actions_text_v1": "",
            "focus_commercial_reported_v2": False,
            "focus_commercial_schema_version_v2": "",
            "focus_commercial_hard_gate_pass_v2": False,
            "focus_commercial_soft_score_v2": 0.0,
            "focus_commercial_confidence_score_v2": 0.0,
            "focus_commercial_overall_score_v2": 0.0,
            "focus_commercial_risk_bucket_v2": "",
            "focus_commercial_decision_class_v2": "",
            "focus_commercial_primary_upgrade_actions_v2": [],
            "focus_commercial_primary_upgrade_actions_text_v2": "",
            "focus_commercial_human_summary_v2": "",
            "focus_translation_gate_version": "",
            "focus_translation_gate_focus_status": "",
            "focus_translation_gate_focus_score": 0.0,
            "focus_translation_gate_focus_reason": "",
            "focus_stronger_physics_shortlist_version": "",
            "focus_shortlist_tier": "",
            "focus_recommended_next_expensive_lane": "",
            "focus_recommended_next_expensive_lane_reason": "",
            "focus_pose_validation_reported": False,
            "focus_pose_validation_version": "",
            "focus_pose_validation_source": "",
            "focus_pose_validation_focus_status": "",
            "focus_pose_validation_focus_soft_status": "",
            "focus_pose_validation_focus_score": 0.0,
            "focus_pose_validation_focus_pass": False,
            "focus_pose_validation_focus_pose_preservation_rmsd_A": None,
            "focus_pose_validation_focus_backmapping_consistency_score": None,
            "focus_pose_validation_focus_thresholds": {},
            "focus_pose_validation_focus_failed_checks": [],
            "focus_pose_validation_focus_missing_checks": [],
            "focus_pose_validation_focus_passed_checks": [],
            "focus_pose_validation_focus_action_codes": [],
            "focus_pose_validation_focus_blocker_codes": [],
            "focus_pose_validation_focus_reason": "",
            "next_required_step": "",
        }
    focus = min(
        members,
        key=lambda member: (
            0 if member["next_required_step"] else 1,
            0 if member["surface_kind"] == "review_packet" else 1,
            member["surface_order"],
        ),
    )
    return {
        "ready": True,
        "target_count": len({_text(member.get("target_id")) for member in members if _text(member.get("target_id"))}),
        "surface_count": len(members),
        "focus_target_id": _text(focus.get("target_id")),
        "focus_surface_label": _text(focus.get("surface_label")),
        "focus_status_line": _text(focus.get("status_line")),
        "focus_commercial_reported_v1": bool(focus.get("commercial_reported_v1", False)),
        "focus_commercial_schema_version": _text(focus.get("commercial_schema_version")),
        "focus_commercial_hard_gate_pass_v1": bool(focus.get("commercial_hard_gate_pass_v1", False)),
        "focus_commercial_overall_score_v1": _safe_float(focus.get("commercial_overall_score_v1"), 0.0),
        "focus_commercial_risk_bucket_v1": _text(focus.get("commercial_risk_bucket_v1")),
        "focus_commercial_decision_class_v1": _text(focus.get("commercial_decision_class_v1")),
        "focus_commercial_primary_upgrade_actions_v1": list(
            focus.get("commercial_primary_upgrade_actions_v1", []) or []
        ),
        "focus_commercial_primary_upgrade_actions_text_v1": _text(
            focus.get("commercial_primary_upgrade_actions_text_v1")
        ),
        "focus_commercial_reported_v2": bool(focus.get("commercial_reported_v2", False)),
        "focus_commercial_schema_version_v2": _text(focus.get("commercial_schema_version_v2")),
        "focus_commercial_hard_gate_pass_v2": bool(focus.get("commercial_hard_gate_pass_v2", False)),
        "focus_commercial_soft_score_v2": _safe_float(focus.get("commercial_soft_score_v2"), 0.0),
        "focus_commercial_confidence_score_v2": _safe_float(
            focus.get("commercial_confidence_score_v2"),
            0.0,
        ),
        "focus_commercial_overall_score_v2": _safe_float(focus.get("commercial_overall_score_v2"), 0.0),
        "focus_commercial_risk_bucket_v2": _text(focus.get("commercial_risk_bucket_v2")),
        "focus_commercial_decision_class_v2": _text(focus.get("commercial_decision_class_v2")),
        "focus_commercial_primary_upgrade_actions_v2": list(
            focus.get("commercial_primary_upgrade_actions_v2", []) or []
        ),
        "focus_commercial_primary_upgrade_actions_text_v2": _text(
            focus.get("commercial_primary_upgrade_actions_text_v2")
        ),
        "focus_commercial_human_summary_v2": _text(focus.get("commercial_human_summary_v2")),
        "focus_translation_gate_version": _text(focus.get("translation_gate_version")),
        "focus_translation_gate_focus_status": _text(focus.get("translation_gate_focus_status")),
        "focus_translation_gate_focus_score": _safe_float(
            focus.get("translation_gate_focus_score"),
            0.0,
        ),
        "focus_translation_gate_focus_reason": _text(focus.get("translation_gate_focus_reason")),
        "focus_stronger_physics_shortlist_version": _text(
            focus.get("stronger_physics_shortlist_version")
        ),
        "focus_shortlist_tier": _text(focus.get("focus_shortlist_tier")),
        "focus_recommended_next_expensive_lane": _text(
            focus.get("recommended_next_expensive_lane")
        ),
        "focus_recommended_next_expensive_lane_reason": _text(
            focus.get("recommended_next_expensive_lane_reason")
        ),
        "focus_pose_validation_reported": bool(focus.get("pose_validation_reported", False)),
        "focus_pose_validation_version": _text(focus.get("pose_validation_version")),
        "focus_pose_validation_source": _text(focus.get("pose_validation_source")),
        "focus_pose_validation_focus_status": _text(focus.get("pose_validation_focus_status")),
        "focus_pose_validation_focus_soft_status": _text(
            focus.get("pose_validation_focus_soft_status")
        ),
        "focus_pose_validation_focus_score": _safe_float(
            focus.get("pose_validation_focus_score"),
            0.0,
        ),
        "focus_pose_validation_focus_pass": bool(
            focus.get("pose_validation_focus_pass", False)
        ),
        "focus_pose_validation_focus_pose_preservation_rmsd_A": focus.get(
            "pose_validation_focus_pose_preservation_rmsd_A"
        ),
        "focus_pose_validation_focus_backmapping_consistency_score": focus.get(
            "pose_validation_focus_backmapping_consistency_score"
        ),
        "focus_pose_validation_focus_thresholds": dict(
            focus.get("pose_validation_focus_thresholds", {}) or {}
        ),
        "focus_pose_validation_focus_failed_checks": list(
            focus.get("pose_validation_focus_failed_checks", []) or []
        ),
        "focus_pose_validation_focus_missing_checks": list(
            focus.get("pose_validation_focus_missing_checks", []) or []
        ),
        "focus_pose_validation_focus_passed_checks": list(
            focus.get("pose_validation_focus_passed_checks", []) or []
        ),
        "focus_pose_validation_focus_action_codes": list(
            focus.get("pose_validation_focus_action_codes", []) or []
        ),
        "focus_pose_validation_focus_blocker_codes": list(
            focus.get("pose_validation_focus_blocker_codes", []) or []
        ),
        "focus_pose_validation_focus_reason": _text(
            focus.get("pose_validation_focus_reason")
        ),
        "next_required_step": _text(focus.get("next_required_step")),
    }


def _selected_allatom_focus_context(
    retry_handoff_summary: dict[str, Any],
    allatom_family_summary: dict[str, Any],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    target_id = _text(
        retry_handoff_summary.get("selected_allatom_target_id"),
        allatom_family_summary.get("focus_target_id"),
    )
    surface_label = _text(
        retry_handoff_summary.get("selected_allatom_surface_label"),
        allatom_family_summary.get("focus_surface_label"),
    )
    focus_available = bool(_text(target_id, surface_label))
    selected_source = next((source for source in sources if source["surface_label"] == surface_label), None)
    if selected_source is None and target_id:
        selected_source = next(
            (
                source
                for source in sources
                if source["target_id"] == target_id and source["surface_kind"] == "review_packet"
            ),
            None,
        )
    if selected_source is None and target_id:
        selected_source = next((source for source in sources if source["target_id"] == target_id), None)

    candidate_sources: list[dict[str, Any]] = []
    if selected_source is not None:
        candidate_sources.append(selected_source)
    if target_id:
        for source in sources:
            if selected_source is not None and source["surface_label"] == selected_source["surface_label"]:
                continue
            if source["target_id"] == target_id:
                candidate_sources.append(source)

    operator_review_reported, operator_review_ready, operator_review_source = _resolve_named_bool_from_specs(
        [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_packet_ready_for_operator_review", "selected_allatom_operator_review_ready", "selected_allatom_packet_ready"))]
        + [
            (source["surface_label"], source["summary"], ("packet_ready_for_operator_review", "packet_ready"))
            for source in candidate_sources
        ]
    )
    wetlab_gate_reported, wetlab_gate_pass, wetlab_gate_source = _resolve_named_bool_from_specs(
        [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_wetlab_gate_pass", "selected_allatom_gate_pass"))]
        + [
            (source["surface_label"], source["summary"], ("wetlab_gate_pass",))
            for source in candidate_sources
        ]
    )
    final_gate_reported, final_gate_pass, final_gate_source = _resolve_named_bool_from_specs(
        [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_wetlab_final_gate_pass", "selected_allatom_final_gate_pass"))]
        + [
            (source["surface_label"], source["summary"], ("wetlab_final_gate_pass", "final_gate_pass"))
            for source in candidate_sources
        ]
    )
    claim_gate_reported, claim_gate_available, claim_gate_source = _resolve_named_bool_from_specs(
        [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_claim_gate_available",))]
        + [
            (source["surface_label"], source["summary"], ("claim_gate_available",))
            for source in candidate_sources
        ]
    )
    claim_ready_reported, claim_ready_for_allatom, claim_ready_source = _resolve_named_bool_from_specs(
        [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_claim_ready_for_allatom",))]
        + [
            (source["surface_label"], source["summary"], ("claim_ready_for_allatom",))
            for source in candidate_sources
        ]
    )
    commercial_reported, commercial_schema_version, commercial_schema_source = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_schema_version",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_schema_version", "allatom_family_focus_commercial_schema_version"))]
    )
    commercial_hard_gate_reported, commercial_hard_gate_value, commercial_hard_gate_source = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_hard_gate_pass_v1",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_hard_gate_pass_v1", "allatom_family_focus_commercial_hard_gate_pass_v1"))]
    )
    commercial_overall_reported, commercial_overall_value, commercial_overall_source = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_overall_score_v1",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_overall_score_v1", "allatom_family_focus_commercial_overall_score_v1"))]
    )
    commercial_risk_reported, commercial_risk_bucket, commercial_risk_source = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_risk_bucket_v1",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_risk_bucket_v1", "allatom_family_focus_commercial_risk_bucket_v1"))]
    )
    commercial_decision_reported, commercial_decision_class, commercial_decision_source = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_decision_class_v1",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_decision_class_v1", "allatom_family_focus_commercial_decision_class_v1"))]
    )
    commercial_actions_reported, commercial_actions_value, commercial_actions_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("commercial_primary_upgrade_actions_v1", "commercial_upgrade_actions_v1"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_primary_upgrade_actions_v1", "allatom_family_focus_commercial_primary_upgrade_actions_v1"))]
    )
    commercial_actions = _normalize_string_list(commercial_actions_value)
    commercial_reported = bool(
        commercial_reported
        or commercial_hard_gate_reported
        or commercial_overall_reported
        or commercial_risk_reported
        or commercial_decision_reported
        or commercial_actions_reported
        or commercial_actions
    )
    commercial_reported_v2, commercial_schema_version_v2, commercial_schema_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_schema_version_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_schema_version_v2", "allatom_family_focus_commercial_schema_version_v2"))]
    )
    commercial_hard_gate_reported_v2, commercial_hard_gate_value_v2, commercial_hard_gate_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_hard_gate_pass_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_hard_gate_pass_v2", "allatom_family_focus_commercial_hard_gate_pass_v2"))]
    )
    commercial_soft_reported_v2, commercial_soft_value_v2, commercial_soft_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_soft_score_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_soft_score_v2", "allatom_family_focus_commercial_soft_score_v2"))]
    )
    commercial_confidence_reported_v2, commercial_confidence_value_v2, commercial_confidence_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_confidence_score_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_confidence_score_v2", "allatom_family_focus_commercial_confidence_score_v2"))]
    )
    commercial_overall_reported_v2, commercial_overall_value_v2, commercial_overall_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_overall_score_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_overall_score_v2", "allatom_family_focus_commercial_overall_score_v2"))]
    )
    commercial_risk_reported_v2, commercial_risk_bucket_v2, commercial_risk_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_risk_bucket_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_risk_bucket_v2", "allatom_family_focus_commercial_risk_bucket_v2"))]
    )
    commercial_decision_reported_v2, commercial_decision_class_v2, commercial_decision_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_decision_class_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_decision_class_v2", "allatom_family_focus_commercial_decision_class_v2"))]
    )
    commercial_actions_reported_v2, commercial_actions_value_v2, commercial_actions_source_v2 = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("commercial_primary_upgrade_actions_v2", "commercial_upgrade_actions_v2"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_primary_upgrade_actions_v2", "allatom_family_focus_commercial_primary_upgrade_actions_v2"))]
    )
    commercial_actions_v2 = _normalize_string_list(commercial_actions_value_v2)
    commercial_human_summary_reported_v2, commercial_human_summary_v2, commercial_human_summary_source_v2 = _resolve_named_value_from_specs(
        [
            (source["surface_label"], source["summary"], ("commercial_human_summary_v2",))
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_commercial_human_summary_v2", "allatom_family_focus_commercial_human_summary_v2"))]
    )
    commercial_reported_v2 = bool(
        commercial_reported_v2
        or commercial_hard_gate_reported_v2
        or commercial_soft_reported_v2
        or commercial_confidence_reported_v2
        or commercial_overall_reported_v2
        or commercial_risk_reported_v2
        or commercial_decision_reported_v2
        or commercial_actions_reported_v2
        or commercial_human_summary_reported_v2
        or commercial_actions_v2
    )
    translation_gate_version_reported, translation_gate_version, translation_gate_version_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("translation_gate_version", "selected_translation_gate_version"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_translation_gate_version", "allatom_family_focus_translation_gate_version"))]
    )
    translation_gate_focus_status_reported, translation_gate_focus_status, translation_gate_focus_status_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("translation_gate_focus_status", "selected_translation_gate_focus_status"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_translation_gate_focus_status", "allatom_family_focus_translation_gate_focus_status"))]
    )
    translation_gate_focus_score_reported, translation_gate_focus_score, translation_gate_focus_score_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("translation_gate_focus_score", "selected_translation_gate_focus_score"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_translation_gate_focus_score", "allatom_family_focus_translation_gate_focus_score"))]
    )
    translation_gate_focus_reason_reported, translation_gate_focus_reason, translation_gate_focus_reason_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("translation_gate_focus_reason", "selected_translation_gate_focus_reason"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_translation_gate_focus_reason", "allatom_family_focus_translation_gate_focus_reason"))]
    )
    shortlist_version_reported, stronger_physics_shortlist_version, stronger_physics_shortlist_version_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("stronger_physics_shortlist_version", "selected_stronger_physics_shortlist_version"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_stronger_physics_shortlist_version", "allatom_family_focus_stronger_physics_shortlist_version"))]
    )
    focus_shortlist_tier_reported, focus_shortlist_tier, focus_shortlist_tier_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("focus_shortlist_tier", "shortlist_tier", "selected_focus_shortlist_tier"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_focus_shortlist_tier", "allatom_family_focus_shortlist_tier"))]
    )
    recommended_lane_reported, recommended_next_expensive_lane, recommended_next_expensive_lane_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("recommended_next_expensive_lane", "focus_recommended_next_expensive_lane"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_recommended_next_expensive_lane", "allatom_family_focus_recommended_next_expensive_lane"))]
    )
    recommended_lane_reason_reported, recommended_next_expensive_lane_reason, recommended_next_expensive_lane_reason_source = _resolve_named_value_from_specs(
        [
            (
                source["surface_label"],
                source["summary"],
                ("recommended_next_expensive_lane_reason", "focus_recommended_next_expensive_lane_reason"),
            )
            for source in candidate_sources
        ]
        + [("retry_handoff_summary", retry_handoff_summary, ("selected_allatom_recommended_next_expensive_lane_reason", "allatom_family_focus_recommended_next_expensive_lane_reason"))]
    )

    selected_summary = dict((selected_source or {}).get("summary", {}) or {})
    pose_validation = _pose_validation_context_from_summary(
        selected_summary,
        source_label=_text((selected_source or {}).get("surface_label")),
    )
    if not pose_validation.get("reported", False):
        for source in candidate_sources:
            candidate_pose_validation = _pose_validation_context_from_summary(
                source.get("summary"),
                source_label=_text(source.get("surface_label")),
            )
            if candidate_pose_validation.get("reported", False):
                pose_validation = candidate_pose_validation
                break
    selected_artifact = _text(
        (selected_source or {}).get("artifact"),
        "runs/wetlab_retry_handoff_summary_current.md" if focus_available else "",
    )
    selected_status = _text(
        selected_summary.get("status"),
        retry_handoff_summary.get("status"),
    )
    selected_command_kind = _text(
        retry_handoff_summary.get("selected_allatom_selected_command_kind"),
        selected_summary.get("selected_command_kind"),
    )
    selected_threshold_A = _safe_float(
        retry_handoff_summary.get("selected_allatom_selected_threshold_A")
        if retry_handoff_summary.get("selected_allatom_selected_threshold_A") not in {"", None}
        else selected_summary.get("selected_threshold_A")
        if selected_summary.get("selected_threshold_A") not in {"", None}
        else selected_summary.get("strict_threshold_A"),
        0.0,
    )
    packet_scope = _text(
        retry_handoff_summary.get("selected_allatom_packet_scope"),
        selected_summary.get("packet_scope"),
    )
    best_compound_name = _text(
        retry_handoff_summary.get("selected_allatom_best_compound_name"),
        selected_summary.get("best_compound_name_human_readable"),
        selected_summary.get("best_compound_name"),
        selected_summary.get("best_ligand_id"),
    )
    best_compound_name_human_readable = _text(
        retry_handoff_summary.get("selected_allatom_best_compound_name_human_readable"),
        selected_summary.get("best_compound_name_human_readable"),
    )
    best_compound_name_resolution = _text(
        retry_handoff_summary.get("selected_allatom_best_compound_name_resolution"),
        selected_summary.get("best_compound_name_resolution"),
        default="unresolved",
    )
    (
        review_packet_best_mean_min_distance_reported,
        review_packet_best_mean_min_distance_A,
        review_packet_best_mean_min_distance_source,
    ) = _selected_review_packet_metric(
        selected_source,
        target_id=target_id,
        surface_label=surface_label,
        metric_key="best_mean_min_distance_A",
    )
    review_packet_authoritative = bool(review_packet_best_mean_min_distance_reported)
    if review_packet_authoritative:
        for key, attr_name in (
            ("packet_ready_for_operator_review", "operator_review_ready"),
            ("wetlab_gate_pass", "wetlab_gate_pass"),
            ("wetlab_final_gate_pass", "final_gate_pass"),
            ("claim_gate_available", "claim_gate_available"),
            ("claim_ready_for_allatom", "claim_ready_for_allatom"),
        ):
            if key not in selected_summary:
                continue
            value = _coerce_boolish(selected_summary.get(key))
            if value is None:
                continue
            if attr_name == "operator_review_ready":
                operator_review_reported = True
                operator_review_ready = value
            elif attr_name == "wetlab_gate_pass":
                wetlab_gate_reported = True
                wetlab_gate_pass = value
            elif attr_name == "final_gate_pass":
                final_gate_reported = True
                final_gate_pass = value
            elif attr_name == "claim_gate_available":
                claim_gate_reported = True
                claim_gate_available = value
            elif attr_name == "claim_ready_for_allatom":
                claim_ready_reported = True
                claim_ready_for_allatom = value
    best_mean_min_distance_A = _safe_float(
        review_packet_best_mean_min_distance_A
        if review_packet_best_mean_min_distance_reported
        else retry_handoff_summary.get("selected_allatom_best_mean_min_distance_A")
        if retry_handoff_summary.get("selected_allatom_best_mean_min_distance_A") not in {"", None}
        else selected_summary.get("best_mean_min_distance_A"),
        0.0,
    )
    best_mean_min_distance_source = _text(
        review_packet_best_mean_min_distance_source,
        retry_handoff_summary.get("selected_allatom_best_mean_min_distance_A_source"),
        (
            "retry_handoff_summary.selected_allatom_best_mean_min_distance_A"
            if retry_handoff_summary.get("selected_allatom_best_mean_min_distance_A") not in {"", None}
            else ""
        ),
        (
            f"{_text((selected_source or {}).get('surface_label'))}.best_mean_min_distance_A"
            if selected_summary.get("best_mean_min_distance_A") not in {"", None}
            else ""
        ),
    )
    promoted_candidate_count = _safe_int(
        selected_summary.get("promoted_candidate_count")
        if review_packet_authoritative and selected_summary.get("promoted_candidate_count") not in {"", None}
        else retry_handoff_summary.get("selected_allatom_promoted_candidate_count")
        if retry_handoff_summary.get("selected_allatom_promoted_candidate_count") not in {"", None}
        else selected_summary.get("promoted_candidate_count"),
        0,
    )
    under_2p5_candidate_count = _safe_int(
        selected_summary.get("under_2p5_candidate_count")
        if review_packet_authoritative and selected_summary.get("under_2p5_candidate_count") not in {"", None}
        else retry_handoff_summary.get("selected_allatom_under_2p5_candidate_count")
        if retry_handoff_summary.get("selected_allatom_under_2p5_candidate_count") not in {"", None}
        else selected_summary.get("under_2p5_candidate_count"),
        0,
    )
    near_candidate_count = _safe_int(
        selected_summary.get("near_candidate_count")
        if review_packet_authoritative and selected_summary.get("near_candidate_count") not in {"", None}
        else retry_handoff_summary.get("selected_allatom_near_candidate_count")
        if retry_handoff_summary.get("selected_allatom_near_candidate_count") not in {"", None}
        else selected_summary.get("near_candidate_count"),
        0,
    )
    next_required_step = _text(
        selected_summary.get("next_required_step") if review_packet_authoritative else "",
        retry_handoff_summary.get("selected_allatom_next_required_step"),
        selected_summary.get("next_required_step") if not review_packet_authoritative else "",
        allatom_family_summary.get("next_required_step"),
    )
    next_required_step = selected_allatom_green_next_required_step(
        wetlab_gate_pass=wetlab_gate_pass,
        final_gate_pass=final_gate_pass,
        claim_ready_for_allatom=claim_ready_for_allatom,
        translation_gate_focus_status=translation_gate_focus_status,
        recommended_next_expensive_lane=recommended_next_expensive_lane,
        fallback_next_required_step=next_required_step,
    )
    readiness_semantics = (
        "operator_review_and_final_gate"
        if final_gate_reported
        else "selected_focus_with_partial_gate_reporting"
        if any(
            (
                operator_review_reported,
                wetlab_gate_reported,
                claim_gate_reported,
                claim_ready_reported,
            )
        )
        else "selected_focus_without_reported_gate_fields"
        if focus_available
        else "not_selected"
    )
    return {
        "focus_available": focus_available,
        "target_id": target_id,
        "surface_label": _text(surface_label, (selected_source or {}).get("surface_label")),
        "selected_summary": selected_summary,
        "selected_command_kind": selected_command_kind,
        "selected_threshold_A": selected_threshold_A,
        "packet_scope": packet_scope,
        "artifact": selected_artifact,
        "status": selected_status,
        "best_compound_name": best_compound_name,
        "best_compound_name_human_readable": best_compound_name_human_readable,
        "best_compound_name_resolution": best_compound_name_resolution,
        "best_mean_min_distance_A": best_mean_min_distance_A,
        "best_mean_min_distance_A_source": best_mean_min_distance_source,
        "promoted_candidate_count": promoted_candidate_count,
        "under_2p5_candidate_count": under_2p5_candidate_count,
        "near_candidate_count": near_candidate_count,
        "next_required_step": next_required_step,
        "readiness_source_surface": _text((selected_source or {}).get("surface_label")),
        "readiness_source_artifact": selected_artifact,
        "readiness_semantics": readiness_semantics,
        "snapshot": {
            "packet_ready_for_operator_review": operator_review_ready,
            "wetlab_gate_pass": wetlab_gate_pass,
            "wetlab_final_gate_pass": final_gate_pass,
            "claim_gate_available": claim_gate_available,
            "claim_ready_for_allatom": claim_ready_for_allatom,
        },
        "reported": {
            "packet_ready_for_operator_review": operator_review_reported,
            "wetlab_gate_pass": wetlab_gate_reported,
            "wetlab_final_gate_pass": final_gate_reported,
            "claim_gate_available": claim_gate_reported,
            "claim_ready_for_allatom": claim_ready_reported,
        },
        "sources": {
            "operator_review": operator_review_source,
            "wetlab_gate": wetlab_gate_source,
            "final_gate": final_gate_source,
            "claim_gate": claim_gate_source,
            "claim_ready": claim_ready_source,
        },
        "commercial": {
            "reported": commercial_reported,
            "schema_version": _text(commercial_schema_version),
            "schema_source": _text(commercial_schema_source),
            "hard_gate_reported": commercial_hard_gate_reported,
            "hard_gate_pass_v1": bool(_coerce_boolish(commercial_hard_gate_value)),
            "hard_gate_source_v1": _text(commercial_hard_gate_source),
            "overall_reported": commercial_overall_reported,
            "overall_score_v1": (
                _safe_float(commercial_overall_value, 0.0)
                if commercial_overall_value is not None and commercial_overall_value != ""
                else 0.0
            ),
            "overall_source_v1": _text(commercial_overall_source),
            "risk_reported": commercial_risk_reported,
            "risk_bucket_v1": _text(commercial_risk_bucket),
            "risk_source_v1": _text(commercial_risk_source),
            "decision_reported": commercial_decision_reported,
            "decision_class_v1": _text(commercial_decision_class),
            "decision_source_v1": _text(commercial_decision_source),
            "primary_upgrade_actions_v1": commercial_actions,
            "primary_upgrade_actions_text_v1": " | ".join(commercial_actions),
            "actions_source_v1": _text(commercial_actions_source),
            "reported_v2": commercial_reported_v2,
            "schema_version_v2": _text(commercial_schema_version_v2),
            "schema_source_v2": _text(commercial_schema_source_v2),
            "hard_gate_reported_v2": commercial_hard_gate_reported_v2,
            "hard_gate_pass_v2": bool(_coerce_boolish(commercial_hard_gate_value_v2)),
            "hard_gate_source_v2": _text(commercial_hard_gate_source_v2),
            "soft_reported_v2": commercial_soft_reported_v2,
            "soft_score_v2": (
                _safe_float(commercial_soft_value_v2, 0.0)
                if commercial_soft_value_v2 is not None and commercial_soft_value_v2 != ""
                else 0.0
            ),
            "soft_source_v2": _text(commercial_soft_source_v2),
            "confidence_reported_v2": commercial_confidence_reported_v2,
            "confidence_score_v2": (
                _safe_float(commercial_confidence_value_v2, 0.0)
                if commercial_confidence_value_v2 is not None and commercial_confidence_value_v2 != ""
                else 0.0
            ),
            "confidence_source_v2": _text(commercial_confidence_source_v2),
            "overall_reported_v2": commercial_overall_reported_v2,
            "overall_score_v2": (
                _safe_float(commercial_overall_value_v2, 0.0)
                if commercial_overall_value_v2 is not None and commercial_overall_value_v2 != ""
                else 0.0
            ),
            "overall_source_v2": _text(commercial_overall_source_v2),
            "risk_reported_v2": commercial_risk_reported_v2,
            "risk_bucket_v2": _text(commercial_risk_bucket_v2),
            "risk_source_v2": _text(commercial_risk_source_v2),
            "decision_reported_v2": commercial_decision_reported_v2,
            "decision_class_v2": _text(commercial_decision_class_v2),
            "decision_source_v2": _text(commercial_decision_source_v2),
            "primary_upgrade_actions_v2": commercial_actions_v2,
            "primary_upgrade_actions_text_v2": " | ".join(commercial_actions_v2),
            "actions_source_v2": _text(commercial_actions_source_v2),
            "human_summary_reported_v2": commercial_human_summary_reported_v2,
            "human_summary_v2": _text(commercial_human_summary_v2),
            "human_summary_source_v2": _text(commercial_human_summary_source_v2),
        },
        "translation": {
            "version_reported": translation_gate_version_reported,
            "version": _text(translation_gate_version),
            "version_source": _text(translation_gate_version_source),
            "focus_status_reported": translation_gate_focus_status_reported,
            "focus_status": _text(translation_gate_focus_status),
            "focus_status_source": _text(translation_gate_focus_status_source),
            "focus_score_reported": translation_gate_focus_score_reported,
            "focus_score": (
                _safe_float(translation_gate_focus_score, 0.0)
                if translation_gate_focus_score is not None and translation_gate_focus_score != ""
                else 0.0
            ),
            "focus_score_source": _text(translation_gate_focus_score_source),
            "focus_reason_reported": translation_gate_focus_reason_reported,
            "focus_reason": _text(translation_gate_focus_reason),
            "focus_reason_source": _text(translation_gate_focus_reason_source),
            "shortlist_version_reported": shortlist_version_reported,
            "stronger_physics_shortlist_version": _text(stronger_physics_shortlist_version),
            "shortlist_version_source": _text(stronger_physics_shortlist_version_source),
            "shortlist_tier_reported": focus_shortlist_tier_reported,
            "focus_shortlist_tier": _text(focus_shortlist_tier),
            "focus_shortlist_tier_source": _text(focus_shortlist_tier_source),
            "recommended_lane_reported": recommended_lane_reported,
            "recommended_next_expensive_lane": _text(recommended_next_expensive_lane),
            "recommended_next_expensive_lane_source": _text(recommended_next_expensive_lane_source),
            "recommended_lane_reason_reported": recommended_lane_reason_reported,
            "recommended_next_expensive_lane_reason": _text(
                recommended_next_expensive_lane_reason
            ),
            "recommended_next_expensive_lane_reason_source": _text(
                recommended_next_expensive_lane_reason_source
            ),
        },
        "pose_validation": pose_validation,
    }


def _selected_allatom_metric_action(metric_name: str) -> tuple[str, str]:
    metric = _text(metric_name)
    if metric == "replicate_count":
        return "increase_replicate_coverage", "expand_replicate_sampling"
    if metric == "replicate_pass_fraction":
        return "raise_replicate_pass_fraction", "recompute_replicate_pass_fraction"
    if metric == "median_mean_min_distance_A":
        return "tighten_replicate_median_geometry", "recompute_median_mean_min_distance_A"
    if metric == "mean_min_distance_iqr_A":
        return "reduce_replicate_distance_dispersion", "recompute_mean_min_distance_iqr_A"
    if metric == "median_contact_fraction":
        return "raise_replicate_contact_occupancy", "recompute_median_contact_fraction"
    if metric == "pose_cluster_dominance":
        return "stabilize_dominant_pose_cluster", "recompute_pose_cluster_dominance"
    if metric == "pose_preservation_rmsd_A":
        return "improve_pose_preservation_rmsd", "recompute_pose_preservation_rmsd_A"
    if metric == "backmapping_consistency_score":
        return "stabilize_backmapping_consistency", "recompute_backmapping_consistency_score"
    if metric == "local_minimization_survival_fraction":
        return "improve_local_minimization_survival", "recompute_local_minimization_survival_fraction"
    if metric == "mean_min_distance_A":
        return "tighten_pose_geometry_under_strict_gate", "recompute_mean_min_distance_A"
    if metric == "binding_energy_proxy":
        return "strengthen_binding_energy_proxy", "recompute_binding_energy_proxy"
    if metric == "stability_score":
        return "raise_trajectory_stability", "recompute_stability_score"
    if metric == "contact_fraction":
        return "raise_contact_occupancy", "recompute_contact_fraction"
    if metric == "binding_energy_mmpbsa_std":
        return "reduce_mmpbsa_uncertainty", "recompute_binding_energy_mmpbsa_std"
    if metric == "trajectory_frames":
        return "increase_trajectory_support", "extend_trajectory_frames"
    return (f"review_{metric}" if metric else "review_metric", f"recompute_{metric}" if metric else "recompute_metric")


def _selected_allatom_metric_threshold_text(metric_name: str, thresholds: dict[str, Any]) -> str:
    metric = _text(metric_name)
    if metric == "replicate_count":
        return _selected_allatom_metric_value_text(thresholds.get("replicate_count_min"))
    if metric == "replicate_pass_fraction":
        return _selected_allatom_metric_value_text(thresholds.get("replicate_pass_fraction_min"))
    if metric in {"median_mean_min_distance_A", "mean_min_distance_A"}:
        return _selected_allatom_metric_value_text(
            thresholds.get("selected_threshold_A") or thresholds.get("strict_threshold_A")
        )
    if metric == "mean_min_distance_iqr_A":
        return _selected_allatom_metric_value_text(thresholds.get("mean_min_distance_iqr_A_max"))
    if metric == "median_contact_fraction":
        return _selected_allatom_metric_value_text(thresholds.get("median_contact_fraction_min"))
    if metric == "pose_cluster_dominance":
        return _selected_allatom_metric_value_text(thresholds.get("pose_cluster_dominance_min"))
    if metric == "pose_preservation_rmsd_A":
        return _selected_allatom_metric_value_text(thresholds.get("pose_preservation_rmsd_A_max"))
    if metric == "backmapping_consistency_score":
        return _selected_allatom_metric_value_text(thresholds.get("backmapping_consistency_score_min"))
    if metric == "local_minimization_survival_fraction":
        return _selected_allatom_metric_value_text(thresholds.get("local_minimization_survival_fraction_min"))
    if metric == "binding_energy_proxy":
        return _selected_allatom_metric_value_text(thresholds.get("binding_energy_proxy_max_kcal_mol"))
    if metric == "stability_score":
        return _selected_allatom_metric_value_text(thresholds.get("stability_score_min"))
    if metric == "contact_fraction":
        return _selected_allatom_metric_value_text(thresholds.get("contact_fraction_min"))
    if metric == "binding_energy_mmpbsa_std":
        return _selected_allatom_metric_value_text(thresholds.get("binding_energy_mmpbsa_std_max"))
    if metric == "trajectory_frames":
        return _selected_allatom_metric_value_text(thresholds.get("trajectory_frames_min"))
    return "missing"


def _selected_allatom_metric_value_text(value: Any) -> str:
    if value in {"", None}:
        return "missing"
    if isinstance(value, bool):
        return str(value).lower()
    try:
        numeric = float(value)
    except Exception:
        return _text(value)
    if numeric.is_integer():
        return f"{numeric:.0f}"
    if abs(numeric) >= 10:
        return f"{numeric:.2f}"
    return f"{numeric:.3f}"


def _selected_allatom_inferred_next_expensive_lane(*texts: Any) -> str:
    combined = " ".join(
        str(text or "").strip().lower() for text in texts if str(text or "").strip()
    )
    if not combined:
        return ""
    if "defer_expensive_lane" in combined or "defer expensive lane" in combined:
        return "defer_expensive_lane"
    if "enter_expensive_lane" in combined or "enter expensive lane" in combined:
        return "enter_expensive_lane"
    return ""


def _selected_allatom_actionability(context: dict[str, Any]) -> dict[str, Any]:
    selected_summary = dict(context.get("selected_summary", {}) or {})
    snapshot = dict(context.get("snapshot", {}) or {})
    reported = dict(context.get("reported", {}) or {})
    translation = dict(context.get("translation", {}) or {})
    commercial = dict(context.get("commercial", {}) or {})

    thresholds = dict(selected_summary.get("commercial_score_thresholds_v2", {}) or {})
    hard_failed_metrics = _normalize_string_list(
        selected_summary.get("commercial_hard_gate_failed_metrics_v2")
        or selected_summary.get("commercial_hard_gate_failed_metrics")
        or []
    )
    hard_missing_metrics = _normalize_string_list(
        selected_summary.get("commercial_hard_gate_missing_metrics_v2")
        or selected_summary.get("commercial_hard_gate_missing_metrics")
        or []
    )
    claim_gate_available = bool(snapshot.get("claim_gate_available", False))
    if not reported.get("claim_gate_available", False) and not claim_gate_available and context.get("focus_available", False):
        claim_gate_available = True
    claim_ready_for_allatom = bool(snapshot.get("claim_ready_for_allatom", False))
    operator_review_ready = bool(snapshot.get("packet_ready_for_operator_review", False))
    wetlab_gate_pass = bool(snapshot.get("wetlab_gate_pass", False))
    final_gate_pass = bool(snapshot.get("wetlab_final_gate_pass", False))
    translation_status = _text(translation.get("focus_status"))
    translation_reason = _text(translation.get("focus_reason"))
    shortlist_tier = _text(translation.get("focus_shortlist_tier"))
    next_expensive_lane = _text(translation.get("recommended_next_expensive_lane"))
    next_expensive_lane_reason = _text(
        translation.get("recommended_next_expensive_lane_reason"),
        translation_reason,
        selected_summary.get("next_required_step"),
    )
    next_required_step = _text(selected_summary.get("next_required_step"))
    commercial_hard_gate_blocked = bool(
        (
            commercial.get("hard_gate_reported_v2", False)
            and not bool(commercial.get("hard_gate_pass_v2", False))
        )
        or (
            commercial.get("hard_gate_reported", False)
            and not bool(commercial.get("hard_gate_pass_v1", False))
        )
    )
    next_expensive_lane = _text(
        next_expensive_lane,
        _selected_allatom_inferred_next_expensive_lane(
            shortlist_tier,
            translation_status,
            next_expensive_lane_reason,
            next_required_step,
        ),
    )

    metric_values = {
        "replicate_count": selected_summary.get("commercial_replicate_count_v2"),
        "replicate_pass_fraction": selected_summary.get("commercial_replicate_pass_fraction_v2"),
        "median_mean_min_distance_A": selected_summary.get("commercial_median_mean_min_distance_A_v2"),
        "mean_min_distance_iqr_A": selected_summary.get("commercial_mean_min_distance_iqr_A_v2"),
        "median_contact_fraction": selected_summary.get("commercial_median_contact_fraction_v2"),
        "pose_cluster_dominance": selected_summary.get("commercial_pose_cluster_dominance_v2"),
        "pose_preservation_rmsd_A": selected_summary.get("commercial_pose_preservation_rmsd_A_v2"),
        "backmapping_consistency_score": selected_summary.get("commercial_backmapping_consistency_score_v2"),
        "local_minimization_survival_fraction": selected_summary.get(
            "commercial_local_minimization_survival_fraction_v2"
        ),
        "mean_min_distance_A": selected_summary.get("selected_allatom_best_mean_min_distance_A")
        or selected_summary.get("commercial_median_mean_min_distance_A_v2"),
        "binding_energy_proxy": selected_summary.get("commercial_binding_energy_proxy_v2"),
        "stability_score": selected_summary.get("commercial_stability_score_v2"),
        "contact_fraction": selected_summary.get("commercial_contact_fraction_v2"),
        "binding_energy_mmpbsa_std": selected_summary.get("commercial_binding_energy_mmpbsa_std_v2"),
        "trajectory_frames": selected_summary.get("commercial_trajectory_frames_v2"),
    }

    hard_block_reason_codes: list[str] = []
    soft_guidance_reason_codes: list[str] = []
    required_calculations: list[str] = []
    action_list: list[dict[str, Any]] = []
    hard_block_present = bool(
        commercial_hard_gate_blocked
        or hard_failed_metrics
        or hard_missing_metrics
        or translation_status in {"fail", "blocked"}
    )
    claim_required_for_final_wetlab = bool(
        selected_summary.get("claim_gate_required_for_final_wetlab", False)
    )
    claim_required_for_commercial_readiness = bool(
        selected_summary.get("claim_gate_required_for_commercial_readiness", False)
    )
    claim_requirement_mode = (
        "semi_hard"
        if (claim_gate_available or claim_required_for_final_wetlab or claim_required_for_commercial_readiness)
        and not hard_block_present
        else "not_applicable"
    )
    claim_requirement_status = (
        "satisfied"
        if claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "blocked"
        if claim_requirement_mode == "semi_hard"
        else "not_applicable"
    )
    claim_requirement_reason = (
        "claim/equivalence gate is satisfied"
        if claim_requirement_mode == "semi_hard" and claim_ready_for_allatom
        else "claim/equivalence gate is semi-hard and blocked"
        if claim_requirement_mode == "semi_hard"
        else "claim/equivalence gate is not applicable"
    )

    if hard_failed_metrics:
        hard_block_reason_codes.extend(f"translation_v2_hard_metric:{metric}" for metric in hard_failed_metrics)
    if hard_missing_metrics:
        hard_block_reason_codes.extend(f"translation_v2_missing_metric:{metric}" for metric in hard_missing_metrics)
    if commercial_hard_gate_blocked:
        hard_block_reason_codes.append("commercial_hard_gate_failed")
    if translation_status:
        soft_guidance_reason_codes.append(f"translation_gate_focus:{translation_status}")
    if shortlist_tier:
        soft_guidance_reason_codes.append(f"shortlist_tier:{shortlist_tier}")
    if next_expensive_lane:
        soft_guidance_reason_codes.append(f"next_expensive_lane:{next_expensive_lane}")
    if claim_requirement_mode == "semi_hard":
        hard_block_reason_codes.append(
            "claim_equivalence_gate_satisfied"
            if claim_ready_for_allatom
            else "claim_equivalence_gate_semi_hard"
        )

    for metric_name in list(dict.fromkeys(hard_failed_metrics + hard_missing_metrics)):
        operation_action, calculation_action = _selected_allatom_metric_action(metric_name)
        value_text = _selected_allatom_metric_value_text(metric_values.get(metric_name))
        threshold_text = _selected_allatom_metric_threshold_text(metric_name, thresholds)
        action_status = "missing" if metric_name in hard_missing_metrics else "failed"
        action_list.append(
            {
                "severity": "hard",
                "category": "translation_v2_metric",
                "action": operation_action,
                "calc_action": calculation_action,
                "status": action_status,
                "metric": metric_name,
                "value": value_text,
                "threshold": threshold_text,
                "reason": f"{metric_name}={value_text}" + (f" threshold={threshold_text}" if threshold_text and threshold_text != "missing" else ""),
                "source": "selected_allatom_focus_summary.commercial_hard_gate_failed_metrics_v2",
            }
        )
        required_calculations.append(calculation_action)

    if claim_requirement_mode == "semi_hard":
        action_list.append(
            {
                "severity": "semi_hard",
                "category": "claim_equivalence",
                "action": "resolve_claim_equivalence_gate",
                "status": "satisfied" if claim_ready_for_allatom else "required",
                "claim_requirement_mode": "semi_hard",
                "reason": claim_requirement_reason,
                "source": _text(selected_summary.get("claim_gate_source"), context.get("readiness_source_surface")),
            }
        )
        if not claim_ready_for_allatom:
            required_calculations.append("resolve_claim_equivalence_gate")

    if next_expensive_lane:
        action_list.append(
            {
                "severity": "soft",
                "category": "next_expensive_lane",
                "action": "defer_expensive_lane" if next_expensive_lane == "defer_expensive_lane" else "enter_expensive_lane",
                "status": "deferred" if next_expensive_lane == "defer_expensive_lane" else "queued",
                "lane": next_expensive_lane,
                "reason": next_expensive_lane_reason,
                "source": _text(translation.get("version"), context.get("readiness_source_surface")),
            }
        )

    hard_block_reason_text = ", ".join(
        part
        for part in [
            "commercial hard gate failed" if commercial_hard_gate_blocked else "",
            "translation v2 hard gate metrics " + ", ".join(hard_failed_metrics) if hard_failed_metrics else "",
            "missing translation v2 metrics " + ", ".join(hard_missing_metrics) if hard_missing_metrics else "",
            claim_requirement_reason if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else "",
        ]
        if part
    )
    soft_guidance_reason_text = ", ".join(
        part for part in soft_guidance_reason_codes if part
    )
    required_calculations = list(dict.fromkeys(required_calculations))
    action_list_text = " | ".join(
        part
        for part in [
            f"{item['severity']}:{item['action']}[{item['status']}]" + (f" lane={item['lane']}" if item.get("lane") else "")
            for item in action_list
        ]
        if part
    )

    if final_gate_pass:
        status = "ready"
    elif hard_block_present:
        status = "hard_blocked"
    elif claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
        status = "semi_hard_blocked"
    elif soft_guidance_reason_codes:
        status = "soft_guided"
    else:
        status = "blocked"

    human_summary = _joined(
        f"{status.replace('_', ' ')}: {hard_block_reason_text}" if hard_block_reason_text else f"{status.replace('_', ' ')}",
        f"required calculations: {', '.join(required_calculations)}" if required_calculations else "",
        f"soft guidance: {soft_guidance_reason_text}" if soft_guidance_reason_text else "",
        f"claim requirement: {claim_requirement_reason}" if claim_requirement_mode == "semi_hard" else "",
        f"next expensive lane: {next_expensive_lane}" if next_expensive_lane else "",
    )
    brief_summary = _joined(
        f"{status.replace('_', ' ')}" if status else "",
        f"hard {', '.join(hard_failed_metrics)}" if hard_failed_metrics else "",
        f"claim {claim_requirement_mode}:{claim_requirement_status}" if claim_requirement_mode else "",
        f"lane {next_expensive_lane}" if next_expensive_lane else "",
    )

    return {
        "status": status,
        "blocked": bool(status != "ready"),
        "block_reason": hard_block_reason_text,
        "block_reason_codes": hard_block_reason_codes,
        "soft_guidance_reasons": soft_guidance_reason_codes,
        "required_calculations": required_calculations,
        "required_calculations_text": ", ".join(required_calculations),
        "action_list": action_list,
        "action_list_text": action_list_text,
        "claim_requirement_mode": claim_requirement_mode,
        "claim_requirement_status": claim_requirement_status,
        "claim_requirement_reason": claim_requirement_reason,
        "next_expensive_lane": next_expensive_lane,
        "next_expensive_lane_reason": next_expensive_lane_reason,
        "translation_gate_v2_failed_metrics": hard_failed_metrics,
        "translation_gate_v2_missing_metrics": hard_missing_metrics,
        "translation_gate_v2_thresholds": thresholds,
        "human_summary": human_summary,
        "brief_summary": brief_summary,
        "provenance": {
            "target_id": _text(context.get("target_id")),
            "surface_label": _text(context.get("surface_label")),
            "readiness_source_surface": _text(context.get("readiness_source_surface")),
            "readiness_source_artifact": _text(context.get("readiness_source_artifact")),
            "commercial_schema_version_v2": _text(commercial.get("schema_version_v2")),
            "translation_gate_version": _text(translation.get("version")),
        },
    }


def _selected_allatom_focus_rows(context: dict[str, Any]) -> list[dict[str, Any]]:
    if not context.get("focus_available", False):
        return []
    operator_review_text, final_gate_text, claim_gate_text = _gate_status_tokens(
        dict(context.get("snapshot", {}) or {}),
        reported=dict(context.get("reported", {}) or {}),
    )
    commercial = dict(context.get("commercial", {}) or {})
    translation = dict(context.get("translation", {}) or {})
    pose_validation = dict(context.get("pose_validation", {}) or {})
    actionability = dict(context.get("actionability", {}) or {})
    return [
        _row(
            group="all-atom refinement/rescue family",
            surface="selected_allatom_focus",
            artifact=_text(context.get("artifact"), default="runs/wetlab_retry_handoff_summary_current.md"),
            status=_text(context.get("status"), default="present"),
            key_signal=_joined(
                context.get("target_id"),
                context.get("surface_label"),
                operator_review_text,
                final_gate_text,
                (
                    f"commercial {_safe_float(commercial.get('overall_score_v1')):.1f}"
                    if bool(commercial.get("reported", False))
                    else ""
                ),
                (
                    f"commercial_v2 {_safe_float(commercial.get('overall_score_v2')):.1f}"
                    if bool(commercial.get("reported_v2", False))
                    else ""
                ),
                _text(commercial.get("risk_bucket_v1")),
                _text(commercial.get("decision_class_v1")),
                _text(translation.get("focus_status")),
                _text(pose_validation.get("focus_status")),
                _text(translation.get("recommended_next_expensive_lane")),
            ),
            one_line_summary=_joined(
                _compound_display_name(
                    context.get("best_compound_name_human_readable"),
                    context.get("best_compound_name"),
                ),
                f"{_safe_float(context.get('best_mean_min_distance_A')):.3f}A"
                if _safe_float(context.get("best_mean_min_distance_A"))
                else "",
                (
                    f"commercial {_safe_float(commercial.get('overall_score_v1')):.1f}"
                    if bool(commercial.get("reported", False))
                    else ""
                ),
                (
                    f"commercial_v2 {_safe_float(commercial.get('overall_score_v2')):.1f}"
                    if bool(commercial.get("reported_v2", False))
                    else ""
                ),
                _text(commercial.get("risk_bucket_v1")),
                _text(commercial.get("decision_class_v1")),
                _text(commercial.get("primary_upgrade_actions_text_v1")),
                _text(commercial.get("decision_class_v2")),
                _text(commercial.get("primary_upgrade_actions_text_v2")),
                _text(translation.get("focus_status")),
                _text(pose_validation.get("focus_status")),
                _text(translation.get("focus_shortlist_tier")),
                _text(translation.get("recommended_next_expensive_lane")),
                _text(actionability.get("brief_summary")),
                claim_gate_text,
                context.get("next_required_step"),
            ),
        )
    ]


def _manual_retry_next_step(
    retry_handoff_summary: dict[str, Any],
    lbdhodh_exploratory_retry_lane: dict[str, Any],
    stk17b_manual_retry_lane: dict[str, Any],
    stk17b_exploratory_retry_lane: dict[str, Any],
    stk17b_exploratory_followup_lane: dict[str, Any],
    plpro_manual_retry_lane: dict[str, Any],
) -> str:
    selected_lane = _select_manual_retry_lane(
        retry_handoff_summary,
        lbdhodh_exploratory_retry_lane,
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
    )
    lane_step = _manual_retry_step_from_lane(selected_lane)
    if lane_step:
        return lane_step
    handoff = _summary(retry_handoff_summary)
    if _text(handoff.get("current_results_next_required_step")):
        return _text(handoff.get("current_results_next_required_step"))
    if _text(handoff.get("next_required_step")):
        return _text(handoff.get("next_required_step"))
    return ""


def _lbdhodh_gate51_validation_review_next_step(validation_review: dict[str, Any] | None) -> str:
    review = _summary(validation_review)
    if _text(review.get("target_id")) != "Leishmania braziliensis DHODH":
        return ""
    if not _text(review.get("decision")):
        return ""
    return _text(review.get("next_required_step"))


def _tcruzi_pde_rescue_review_next_step(review_surface: dict[str, Any] | None) -> str:
    review = _summary(review_surface)
    if _text(review.get("target_id")) != "T. cruzi PDE":
        return ""
    if not _text(review.get("decision")):
        return ""
    return _text(review.get("next_required_step"))


def _tcruzi_pde_rescue_only_branch_next_step(branch_summary: dict[str, Any] | None) -> str:
    branch = _summary(branch_summary)
    if _text(branch.get("target_id")) != "T. cruzi PDE":
        return ""
    if not bool(branch.get("branch_to_rescue_only", False)):
        return ""
    return _text(branch.get("next_required_step"))


def _stk17b_followup_review_next_step(review_surface: dict[str, Any] | None) -> str:
    review = _summary(review_surface)
    if _text(review.get("target_id")) != "STK17B (DRAK2)":
        return ""
    if not _text(review.get("decision")):
        return ""
    return _text(review.get("next_required_step"))


def _campaign_summary_rows(
    partnering_stack: dict[str, Any],
    master_handoff_dashboard: dict[str, Any],
    final_campaign_summary: dict[str, Any],
    master_terminal_review: dict[str, Any],
    retry_handoff_summary: dict[str, Any],
    lbdhodh_exploratory_retry_lane: dict[str, Any],
    stk17b_manual_retry_lane: dict[str, Any],
    stk17b_exploratory_retry_lane: dict[str, Any],
    stk17b_exploratory_followup_lane: dict[str, Any],
    plpro_manual_retry_lane: dict[str, Any],
) -> list[dict[str, Any]]:
    p = _partnering_stack_summary(partnering_stack)
    h = _summary(master_handoff_dashboard)
    f = _summary(final_campaign_summary)
    t = _summary(master_terminal_review)
    manual_retry_step = _manual_retry_next_step(
        retry_handoff_summary,
        lbdhodh_exploratory_retry_lane,
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
    )
    return [
        _row(
            group="stack/handoff/final summary",
            surface="partnering_stack",
            artifact="runs/wetlab_partnering_stack_current.md",
            status=_text(p.get("status"), default="missing"),
            key_signal=_joined(p.get("campaign_terminal_state"), p.get("broad_screen_first_actionable_target_id"), p.get("broad_screen_first_actionable_shard_id")),
            one_line_summary=_joined(p.get("campaign_terminal_state"), p.get("next_required_step")),
        ),
        _row(
            group="stack/handoff/final summary",
            surface="master_handoff_dashboard",
            artifact="runs/wetlab_master_handoff_dashboard_current.md",
            status=_text(h.get("status"), default="missing"),
            key_signal=_joined(h.get("campaign_terminal_state"), h.get("broad_screen_first_actionable_target_id"), h.get("broad_screen_first_actionable_shard_id")),
            one_line_summary=_joined(h.get("primary_surface_artifact"), h.get("next_required_step")),
        ),
        _row(
            group="stack/handoff/final summary",
            surface="final_campaign_summary",
            artifact="runs/wetlab_final_campaign_summary_current.md",
            status=_text(f.get("status"), default="missing"),
            key_signal=_joined(f.get("campaign_terminal_state"), f.get("broad_screen_first_actionable_target_id"), f.get("broad_screen_first_actionable_shard_id")),
            one_line_summary=_joined(f.get("campaign_terminal_state"), f.get("next_required_step")),
        ),
        _row(
            group="stack/handoff/final summary",
            surface="master_terminal_review",
            artifact="runs/wetlab_master_terminal_review_current.md",
            status=_text(t.get("status"), default="missing"),
            key_signal=_joined(t.get("campaign_terminal_state"), t.get("ready_to_send_track_count")),
            one_line_summary=_joined(t.get("campaign_terminal_state"), _text(manual_retry_step, t.get("next_required_step"))),
        ),
    ]


def _render_table(rows: list[dict[str, Any]]) -> str:
    headers = ["Surface", "Artifact", "Status", "Key Signal", "One-Line Summary"]
    columns = ["surface", "artifact", "status", "key_signal", "one_line_summary"]

    def cell(row: dict[str, Any], column: str) -> str:
        return _clean(row.get(column, ""))

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell(row, column) for column in columns) + " |")
    return "\n".join(lines)


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    groups = list(payload.get("groups", []) or [])
    lines = ["# Wet-Lab Current Results Index", ""]
    for key in (
        "status",
        "group_count",
        "surface_count",
        "primary_queue_first_actionable_target_id",
        "primary_queue_first_actionable_shard_id",
        "counter_queue_first_actionable_primary_target_id",
        "counter_queue_first_actionable_anti_target_id",
        "primary_watch_loop_pid",
        "primary_watch_loop_attached",
        "primary_watch_loop_liveness",
        "primary_watch_loop_fallback_mode",
        "antitarget_watch_loop_pid",
        "antitarget_watch_loop_attached",
        "antitarget_watch_loop_liveness",
        "antitarget_watch_loop_fallback_mode",
        "precision_monitor_completion_pct",
        "precision_monitor_successful_completion_pct",
        "precision_monitor_held_completion_pct",
        "failure_surface_auto_hold_row_count",
        "hold_guard_blocked_target_id",
        "hold_guard_streak",
        "hold_guard_limit",
        "dpre1_branch_review_ready",
        "dpre1_branch_review_target_id",
        "dpre1_branch_review_branch_label",
        "dpre1_branch_review_branch_state",
        "dpre1_branch_review_source_priority",
        "dpre1_branch_review_stage6_tuning_recommended_threshold_A",
        "dpre1_branch_review_stage6_tuning_immediately_runnable_command_kind",
        "dpre1_branch_review_exploratory_retry_lane_label",
        "dpre1_branch_review_successor_target",
        "plpro_manual_retry_target_id",
        "plpro_manual_retry_shard_id",
        "plpro_manual_retry_selected_command_kind",
        "stk17b_exploratory_retry_target_id",
        "stk17b_exploratory_retry_shard_id",
        "stk17b_exploratory_retry_selected_command_kind",
        "mapping_fix_retry_support_ready",
        "mapping_fix_retry_ready_target_count",
        "mapping_fix_retry_ready_targets",
        "stage1_mapping_fix_lanes_ready",
        "stage1_mapping_fix_ready_target_count",
        "stage1_mapping_fix_ready_targets",
        "tcruzi_pde_promoted_top4_review_packet_ready",
        "tcruzi_pde_promoted_top4_review_packet_operator_review_ready",
        "tcruzi_pde_promoted_top4_review_packet_wetlab_gate_pass",
        "tcruzi_pde_promoted_top4_review_packet_wetlab_final_gate_pass",
        "tcruzi_pde_promoted_top4_review_packet_claim_gate_available",
        "tcruzi_pde_promoted_top4_review_packet_claim_ready_for_allatom",
        "tcruzi_pde_promoted_top4_review_packet_target_id",
        "tcruzi_pde_promoted_top4_review_packet_shard_id",
        "tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count",
        "tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count",
        "tcruzi_pde_promoted_top4_review_packet_selected_command_kind",
        "tcruzi_pde_promoted_top4_review_packet_strict_threshold_A",
        "tcruzi_pde_promoted_top4_review_packet_best_ligand_id",
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name",
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable",
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution",
        "tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A",
        "tcruzi_pde_promoted_top4_review_packet_next_required_step",
        "tcruzi_pde_rescue_only_branch_summary_ready",
        "tcruzi_pde_rescue_only_branch_summary_operator_review_ready",
        "tcruzi_pde_rescue_only_branch_summary_wetlab_gate_pass",
        "tcruzi_pde_rescue_only_branch_summary_wetlab_final_gate_pass",
        "tcruzi_pde_rescue_only_branch_summary_claim_gate_available",
        "tcruzi_pde_rescue_only_branch_summary_claim_ready_for_allatom",
        "tcruzi_pde_rescue_only_branch_summary_target_id",
        "tcruzi_pde_rescue_only_branch_summary_shard_id",
        "tcruzi_pde_rescue_only_branch_summary_branch_state",
        "tcruzi_pde_rescue_only_branch_summary_default_lane_reopen_allowed",
        "tcruzi_pde_rescue_only_branch_summary_branch_to_rescue_only",
        "tcruzi_pde_rescue_only_branch_summary_selected_command_kind",
        "tcruzi_pde_rescue_only_branch_summary_selected_threshold_A",
        "tcruzi_pde_rescue_only_branch_summary_promoted_top4_packet_ready",
        "tcruzi_pde_rescue_only_branch_summary_promoted_candidate_count",
        "tcruzi_pde_rescue_only_branch_summary_under_2p5_candidate_count",
        "tcruzi_pde_rescue_only_branch_summary_best_ligand_id",
        "tcruzi_pde_rescue_only_branch_summary_best_compound_name",
        "tcruzi_pde_rescue_only_branch_summary_best_compound_name_human_readable",
        "tcruzi_pde_rescue_only_branch_summary_best_compound_name_resolution",
        "tcruzi_pde_rescue_only_branch_summary_best_mean_min_distance_A",
        "tcruzi_pde_rescue_only_branch_summary_next_required_step",
        "selected_rescue_review_best_compound_name",
        "selected_rescue_review_best_compound_name_human_readable",
        "selected_rescue_review_best_compound_name_resolution",
        "selected_rescue_branch_target_id",
        "selected_rescue_branch_surface_label",
        "selected_rescue_branch_shard_id",
        "selected_rescue_branch_selected_command_kind",
        "selected_rescue_branch_best_compound_name",
        "selected_rescue_branch_best_compound_name_human_readable",
        "selected_rescue_branch_best_compound_name_resolution",
        "selected_rescue_branch_selected_threshold_A",
        "selected_rescue_branch_promoted_candidate_count",
        "selected_rescue_branch_under_2p5_candidate_count",
        "selected_rescue_branch_operator_review_ready",
        "selected_rescue_branch_wetlab_gate_pass",
        "selected_rescue_branch_wetlab_final_gate_pass",
        "selected_rescue_branch_claim_gate_available",
        "selected_rescue_branch_claim_ready_for_allatom",
        "selected_rescue_branch_operator_packet_ready",
        "selected_rescue_branch_operator_packet_wetlab_gate_pass",
        "selected_rescue_branch_operator_packet_wetlab_final_gate_pass",
        "selected_rescue_branch_operator_packet_claim_gate_available",
        "selected_rescue_branch_operator_packet_claim_ready_for_allatom",
        "selected_rescue_branch_next_required_step",
        "allatom_family_focus_commercial_reported_v1",
        "allatom_family_focus_commercial_schema_version",
        "allatom_family_focus_commercial_hard_gate_pass_v1",
        "allatom_family_focus_commercial_overall_score_v1",
        "allatom_family_focus_commercial_risk_bucket_v1",
        "allatom_family_focus_commercial_decision_class_v1",
        "allatom_family_focus_commercial_primary_upgrade_actions_v1",
        "allatom_family_focus_commercial_primary_upgrade_actions_text_v1",
        "allatom_family_focus_commercial_reported_v2",
        "allatom_family_focus_commercial_schema_version_v2",
        "allatom_family_focus_commercial_hard_gate_pass_v2",
        "allatom_family_focus_commercial_soft_score_v2",
        "allatom_family_focus_commercial_confidence_score_v2",
        "allatom_family_focus_commercial_overall_score_v2",
        "allatom_family_focus_commercial_risk_bucket_v2",
        "allatom_family_focus_commercial_decision_class_v2",
        "allatom_family_focus_commercial_primary_upgrade_actions_v2",
        "allatom_family_focus_commercial_primary_upgrade_actions_text_v2",
        "allatom_family_focus_commercial_human_summary_v2",
        "allatom_family_focus_translation_gate_version",
        "allatom_family_focus_translation_gate_focus_status",
        "allatom_family_focus_translation_gate_focus_score",
        "allatom_family_focus_translation_gate_focus_reason",
        "allatom_family_focus_pose_validation_reported",
        "allatom_family_focus_pose_validation_version",
        "allatom_family_focus_pose_validation_source",
        "allatom_family_focus_pose_validation_status",
        "allatom_family_focus_pose_validation_soft_status",
        "allatom_family_focus_pose_validation_score",
        "allatom_family_focus_pose_validation_pass",
        "allatom_family_focus_pose_validation_pose_preservation_rmsd_A",
        "allatom_family_focus_pose_validation_backmapping_consistency_score",
        "allatom_family_focus_pose_validation_thresholds",
        "allatom_family_focus_pose_validation_failed_checks",
        "allatom_family_focus_pose_validation_missing_checks",
        "allatom_family_focus_pose_validation_passed_checks",
        "allatom_family_focus_pose_validation_action_codes",
        "allatom_family_focus_pose_validation_blocker_codes",
        "allatom_family_focus_pose_validation_reason",
        "allatom_family_focus_shortlist_tier",
        "allatom_family_focus_recommended_next_expensive_lane",
        "allatom_family_focus_recommended_next_expensive_lane_reason",
        "selected_allatom_focus_available",
        "selected_allatom_focus_artifact",
        "selected_allatom_focus_status",
        "selected_allatom_readiness_source_surface",
        "selected_allatom_readiness_source_artifact",
        "selected_allatom_readiness_semantics",
        "selected_allatom_operator_review_ready_reported",
        "selected_allatom_operator_review_ready",
        "selected_allatom_wetlab_gate_reported",
        "selected_allatom_wetlab_gate_pass",
        "selected_allatom_final_gate_reported",
        "selected_allatom_final_gate_pass",
        "selected_allatom_final_wetlab_ready",
        "selected_allatom_claim_gate_available_reported",
        "selected_allatom_claim_gate_available",
        "selected_allatom_claim_ready_for_allatom_reported",
        "selected_allatom_claim_ready_for_allatom",
        "selected_allatom_target_id",
        "selected_allatom_surface_label",
        "selected_allatom_selected_command_kind",
        "selected_allatom_selected_threshold_A",
        "selected_allatom_packet_scope",
        "selected_allatom_best_compound_name",
        "selected_allatom_best_compound_name_human_readable",
        "selected_allatom_best_compound_name_resolution",
        "selected_allatom_best_mean_min_distance_A",
        "selected_allatom_best_mean_min_distance_A_source",
        "selected_allatom_promoted_candidate_count",
        "selected_allatom_under_2p5_candidate_count",
        "selected_allatom_near_candidate_count",
        "selected_allatom_next_required_step",
        "selected_allatom_actionability_status",
        "selected_allatom_actionability_brief_summary",
        "selected_allatom_actionability_human_summary",
        "selected_allatom_human_summary",
        "selected_allatom_actionability_block_reason",
        "selected_allatom_actionability_block_reason_codes",
        "selected_allatom_actionability_soft_guidance_reasons",
        "selected_allatom_actionability_required_calculations_text",
        "selected_allatom_actionability_action_list_text",
        "selected_allatom_actionability_claim_requirement_mode",
        "selected_allatom_actionability_claim_requirement_status",
        "selected_allatom_actionability_claim_requirement_reason",
        "selected_allatom_actionability_next_expensive_lane",
        "selected_allatom_actionability_next_expensive_lane_reason",
        "selected_allatom_actionability_translation_gate_v2_failed_metrics",
        "selected_allatom_actionability_translation_gate_v2_missing_metrics",
        "selected_allatom_actionability_translation_gate_v2_thresholds",
        "selected_allatom_claim_gate_source",
        "selected_allatom_claim_gate_policy_version",
        "selected_allatom_claim_pass_core_gate",
        "selected_allatom_claim_core_failed_metrics",
        "selected_allatom_claim_core_missing_metrics",
        "selected_allatom_claim_failed_metrics",
        "selected_allatom_claim_missing_metrics",
        "selected_allatom_claim_requirement_mode",
        "selected_allatom_claim_requirement_provenance",
        "selected_allatom_claim_required_for_final_wetlab",
        "selected_allatom_claim_required_for_commercial_readiness",
        "selected_allatom_claim_requirement_reason",
        "selected_allatom_claim_requirement_actions",
        "selected_allatom_commercial_replicate_count_v2",
        "selected_allatom_commercial_replicate_pass_fraction_v2",
        "selected_allatom_commercial_median_mean_min_distance_A_v2",
        "selected_allatom_commercial_mean_min_distance_iqr_A_v2",
        "selected_allatom_commercial_median_contact_fraction_v2",
        "selected_allatom_commercial_pose_cluster_dominance_v2",
        "selected_allatom_commercial_pose_preservation_rmsd_A_v2",
        "selected_allatom_commercial_backmapping_consistency_score_v2",
        "selected_allatom_commercial_local_minimization_survival_fraction_v2",
        "selected_allatom_commercial_binding_energy_proxy_v2",
        "selected_allatom_commercial_stability_score_v2",
        "selected_allatom_commercial_contact_fraction_v2",
        "selected_allatom_commercial_binding_energy_mmpbsa_std_v2",
        "selected_allatom_commercial_trajectory_frames_v2",
        "selected_allatom_commercial_hard_gate_failed_metrics_v2",
        "selected_allatom_commercial_hard_gate_missing_metrics_v2",
        "selected_allatom_commercial_score_thresholds_v2",
        "selected_allatom_commercial_reported_v1",
        "selected_allatom_commercial_schema_version",
        "selected_allatom_commercial_hard_gate_reported_v1",
        "selected_allatom_commercial_hard_gate_pass_v1",
        "selected_allatom_commercial_overall_reported_v1",
        "selected_allatom_commercial_overall_score_v1",
        "selected_allatom_commercial_risk_reported_v1",
        "selected_allatom_commercial_risk_bucket_v1",
        "selected_allatom_commercial_decision_reported_v1",
        "selected_allatom_commercial_decision_class_v1",
        "selected_allatom_commercial_primary_upgrade_actions_v1",
        "selected_allatom_commercial_primary_upgrade_actions_text_v1",
        "selected_allatom_commercial_reported_v2",
        "selected_allatom_commercial_schema_version_v2",
        "selected_allatom_commercial_hard_gate_pass_v2",
        "selected_allatom_commercial_soft_score_v2",
        "selected_allatom_commercial_confidence_score_v2",
        "selected_allatom_commercial_overall_score_v2",
        "selected_allatom_commercial_risk_bucket_v2",
        "selected_allatom_commercial_decision_class_v2",
        "selected_allatom_commercial_primary_upgrade_actions_v2",
        "selected_allatom_commercial_primary_upgrade_actions_text_v2",
        "selected_allatom_commercial_human_summary_v2",
        "selected_allatom_translation_gate_version",
        "selected_allatom_translation_gate_focus_status",
        "selected_allatom_translation_gate_focus_score",
        "selected_allatom_translation_gate_focus_reason",
        "selected_allatom_pose_validation_reported",
        "selected_allatom_pose_validation_version",
        "selected_allatom_pose_validation_source",
        "selected_allatom_pose_validation_status",
        "selected_allatom_pose_validation_soft_status",
        "selected_allatom_pose_validation_score",
        "selected_allatom_pose_validation_pass",
        "selected_allatom_pose_validation_pose_preservation_rmsd_A",
        "selected_allatom_pose_validation_backmapping_consistency_score",
        "selected_allatom_pose_validation_thresholds",
        "selected_allatom_pose_validation_failed_checks",
        "selected_allatom_pose_validation_missing_checks",
        "selected_allatom_pose_validation_passed_checks",
        "selected_allatom_pose_validation_action_codes",
        "selected_allatom_pose_validation_blocker_codes",
        "selected_allatom_pose_validation_reason",
        "selected_allatom_focus_shortlist_tier",
        "selected_allatom_recommended_next_expensive_lane",
        "selected_allatom_recommended_next_expensive_lane_reason",
        "hard_target_rescue_lane_ready",
        "hard_target_rescue_lane_target_id",
        "hard_target_rescue_lane_shard_id",
        "hard_target_rescue_lane_auto_hold_streak",
        "hard_target_rescue_lane_selected_command_kind",
        "hard_target_rescue_lane_lane_label",
        "rescue_anchor_artifacts_ready",
        "rescue_anchor_target_id",
        "rescue_anchor_artifact_count",
        "rescue_anchor_rescue_only",
        "rescue_three_bead_candidates_ready",
        "rescue_three_bead_candidate_target_id",
        "rescue_three_bead_candidate_count",
        "rescue_three_bead_candidate_top_n",
        "rescue_three_bead_candidate_selected_command_kind",
        "ligand_admet_module_ready",
        "ligand_admet_module_status",
        "ligand_admet_target_count",
        "ligand_admet_compound_count",
        "ligand_admet_green_count",
        "ligand_admet_yellow_count",
        "ligand_admet_red_count",
        "ligand_admet_module_scope",
        "ligand_admet_next_required_step",
        "partnering_stack_artifact_status",
        "partnering_stack_artifact_complete",
        "campaign_terminal_state",
        "ready_to_send_track_count",
        "next_required_step",
    ):
        if key in summary:
            lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(["", "## Groups", ""])
    for group in groups:
        group_name = str(group.get("group", "")).strip()
        group_signal = str(group.get("group_signal", "")).strip()
        lines.append(f"### {group_name}")
        if group_signal:
            lines.append("")
            lines.append(f"- group_signal: `{group_signal}`")
        lines.append("")
        lines.append(_render_table(list(group.get("rows", []) or [])))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_index_artifact(md_path_like: str, payload: dict[str, Any]) -> None:
    md_path = resolve(md_path_like)
    json_path = md_path.with_suffix(".json")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")


def build_payload(
    primary_queue: dict[str, Any] | None = None,
    antitarget_queue: dict[str, Any] | None = None,
    primary_watch_state: dict[str, Any] | None = None,
    antitarget_watch_state: dict[str, Any] | None = None,
    precision_monitor: dict[str, Any] | None = None,
    failure_surface: dict[str, Any] | None = None,
    primary_retry_preset: dict[str, Any] | None = None,
    antitarget_retry_preset: dict[str, Any] | None = None,
    hold_guard: dict[str, Any] | None = None,
    retry_handoff_summary: dict[str, Any] | None = None,
    dpre1_branch_review_surface: dict[str, Any] | None = None,
    dengue_stage6_tuning_surface: dict[str, Any] | None = None,
    dengue_exploratory_retry_lane: dict[str, Any] | None = None,
    lbdhodh_gate51_validation_review_surface: dict[str, Any] | None = None,
    tcruzi_pde_rescue_review_surface: dict[str, Any] | None = None,
    tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None = None,
    tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None = None,
    lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    stk17b_manual_retry_lane: dict[str, Any] | None = None,
    stk17b_exploratory_retry_lane: dict[str, Any] | None = None,
    stk17b_exploratory_followup_lane: dict[str, Any] | None = None,
    stk17b_followup_review_surface: dict[str, Any] | None = None,
    kinase_retry_policy_templates: dict[str, Any] | None = None,
    target_retry_policy_templates: dict[str, Any] | None = None,
    plpro_manual_retry_lane: dict[str, Any] | None = None,
    mapping_fix_retry_support: dict[str, Any] | None = None,
    stage1_mapping_fix_lanes: dict[str, Any] | None = None,
    mapping_fix_retry_policy_templates: dict[str, Any] | None = None,
    hard_target_rescue_lane: dict[str, Any] | None = None,
    rescue_anchor_artifacts: dict[str, Any] | None = None,
    rescue_three_bead_candidates: dict[str, Any] | None = None,
    partnering_stack: dict[str, Any] | None = None,
    master_handoff_dashboard: dict[str, Any] | None = None,
    final_campaign_summary: dict[str, Any] | None = None,
    master_terminal_review: dict[str, Any] | None = None,
    tcruzi_krs1_branch_review_surface: dict[str, Any] | None = None,
    tcruzi_pde_allatom_rescue_lane: dict[str, Any] | None = None,
    tcruzi_pde_allatom_review_packet: dict[str, Any] | None = None,
    cathepsin_k_allatom_refinement_lane: dict[str, Any] | None = None,
    cathepsin_k_allatom_review_packet: dict[str, Any] | None = None,
    sarscov2_mpro_allatom_refinement_lane: dict[str, Any] | None = None,
    sarscov2_mpro_allatom_review_packet: dict[str, Any] | None = None,
    selected_allatom_visual_bundle: dict[str, Any] | None = None,
    ligand_admet_module: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rh = _summary(retry_handoff_summary or {})
    primary_rows = _primary_queue_rows(primary_queue or {}, antitarget_queue or {})
    watch_rows = _watch_state_rows(primary_watch_state or {}, antitarget_watch_state or {})
    precision_rows = _precision_monitor_rows(precision_monitor or {})
    failure_rows = _failure_surface_rows(failure_surface or {})
    retry_rows = _retry_preset_rows(primary_retry_preset or {}, antitarget_retry_preset or {})
    hold_rows = _hold_guard_rows(hold_guard or {})
    validation_review_rows = _lbdhodh_gate51_validation_review_rows(lbdhodh_gate51_validation_review_surface or {})
    pqs = _summary(primary_queue or {})
    aqs = _summary(antitarget_queue or {})
    pm = _summary(precision_monitor or {})
    primary_focus_target = _text(pm.get("focus_target_id"), pqs.get("first_actionable_target_id"))
    primary_focus_shard = _text(pm.get("focus_shard_id"), pqs.get("first_actionable_shard_id"))
    primary_focus_queue_status = _text(pm.get("focus_queue_status"), pqs.get("first_actionable_queue_status"))
    krs1_branch_review = _summary(tcruzi_krs1_branch_review_surface or {})
    krs1_branch_review_ready = _text(krs1_branch_review.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
    krs1_branch_review_selected = bool(krs1_branch_review_ready and primary_focus_target == "T. cruzi KRS1")
    selected_krs1_branch_review_next_required_step = (
        _text(krs1_branch_review.get("next_required_step")) if krs1_branch_review_selected else ""
    )
    krs1_branch_review_rows = _krs1_branch_review_rows(
        tcruzi_krs1_branch_review_surface or {},
        selected=krs1_branch_review_selected,
    )
    dpre1_branch_review_rows = _dpre1_branch_review_rows(dpre1_branch_review_surface or {})
    tcruzi_pde_rescue_review_rows = _tcruzi_pde_rescue_review_rows(tcruzi_pde_rescue_review_surface or {})
    tcruzi_pde_promoted_top4_review_packet_rows = _tcruzi_pde_promoted_top4_review_packet_rows(
        tcruzi_pde_promoted_top4_review_packet or {}
    )
    tcruzi_pde_rescue_only_branch_summary_rows = _tcruzi_pde_rescue_only_branch_summary_rows(
        tcruzi_pde_rescue_only_branch_summary or {}
    )
    tcruzi_pde_rescue_rows = (
        tcruzi_pde_rescue_review_rows
        + tcruzi_pde_promoted_top4_review_packet_rows
        + tcruzi_pde_rescue_only_branch_summary_rows
    )
    dengue_stage6_rows = _dengue_stage6_rows(primary_queue or {}, dengue_stage6_tuning_surface or {}, dengue_exploratory_retry_lane or {})
    manual_retry_rows = _manual_retry_lane_rows(
        retry_handoff_summary or {},
        lbdhodh_exploratory_retry_lane or {},
        stk17b_manual_retry_lane or {},
        stk17b_exploratory_retry_lane or {},
        stk17b_exploratory_followup_lane or {},
        plpro_manual_retry_lane or {},
        mapping_fix_retry_support or {},
        stage1_mapping_fix_lanes or {},
    )
    kinase_template_rows = _kinase_retry_template_rows(kinase_retry_policy_templates or {})
    target_retry_template_rows = _target_retry_template_rows(target_retry_policy_templates or {})
    stage6_retry_template_rows = _stage6_retry_template_rows(target_retry_policy_templates or {})
    mapping_fix_template_rows = _mapping_fix_retry_template_rows(mapping_fix_retry_policy_templates or {})
    hard_target_rescue_lane_rows = _hard_target_rescue_lane_rows(hard_target_rescue_lane or {})
    rescue_anchor_artifacts_rows = _rescue_anchor_artifacts_rows(rescue_anchor_artifacts or {})
    rescue_three_bead_candidates_rows = _rescue_three_bead_candidates_rows(rescue_three_bead_candidates or {})
    ligand_admet_rows = _ligand_admet_module_rows(ligand_admet_module or {})
    allatom_family_rows = _allatom_family_rows(
        tcruzi_pde_allatom_rescue_lane or {},
        tcruzi_pde_allatom_review_packet or {},
        cathepsin_k_allatom_refinement_lane or {},
        cathepsin_k_allatom_review_packet or {},
        sarscov2_mpro_allatom_refinement_lane or {},
        sarscov2_mpro_allatom_review_packet or {},
    )
    allatom_family_summary = _allatom_family_summary(
        tcruzi_pde_allatom_rescue_lane or {},
        tcruzi_pde_allatom_review_packet or {},
        cathepsin_k_allatom_refinement_lane or {},
        cathepsin_k_allatom_review_packet or {},
        sarscov2_mpro_allatom_refinement_lane or {},
        sarscov2_mpro_allatom_review_packet or {},
    )
    allatom_surface_sources = _allatom_surface_sources(
        tcruzi_pde_allatom_rescue_lane or {},
        tcruzi_pde_allatom_review_packet or {},
        cathepsin_k_allatom_refinement_lane or {},
        cathepsin_k_allatom_review_packet or {},
        sarscov2_mpro_allatom_refinement_lane or {},
        sarscov2_mpro_allatom_review_packet or {},
    )
    selected_allatom_focus_context = _selected_allatom_focus_context(
        rh,
        allatom_family_summary,
        allatom_surface_sources,
    )
    selected_allatom_selected_summary = dict(selected_allatom_focus_context.get("selected_summary", {}) or {})
    selected_allatom_canonical = resolve_selected_allatom_canonical(
        review_packet_summary=selected_allatom_selected_summary,
        retry_handoff_summary=rh,
        next_required_step=_text(selected_allatom_focus_context.get("next_required_step")),
    )
    selected_allatom_visual = resolve_selected_allatom_visual_bundle(
        selected_allatom_visual_bundle
    )
    selected_allatom_visual_fields = selected_allatom_visual_surface_fields(
        selected_allatom_visual
    )
    selected_allatom_actionability = dict(
        selected_allatom_canonical.get("effective_actionability", {}) or {}
    )
    selected_allatom_focus_context = {
        **selected_allatom_focus_context,
        "commercial": {
            **dict(selected_allatom_focus_context.get("commercial", {}) or {}),
            **dict(selected_allatom_canonical.get("commercial", {}) or {}),
        },
        "translation": {
            **dict(selected_allatom_focus_context.get("translation", {}) or {}),
            **dict(selected_allatom_canonical.get("translation", {}) or {}),
        },
        "raw_claim": dict(selected_allatom_canonical.get("raw_claim", {}) or {}),
        "actionability": selected_allatom_actionability,
        "canonical": selected_allatom_canonical,
    }
    selected_allatom_focus_rows = _selected_allatom_focus_rows(selected_allatom_focus_context)
    allatom_group_rows = selected_allatom_focus_rows + allatom_family_rows
    campaign_rows = _campaign_summary_rows(
        partnering_stack or {},
        master_handoff_dashboard or {},
        final_campaign_summary or {},
        master_terminal_review or {},
        retry_handoff_summary or {},
        lbdhodh_exploratory_retry_lane or {},
        stk17b_manual_retry_lane or {},
        stk17b_exploratory_retry_lane or {},
        stk17b_exploratory_followup_lane or {},
        plpro_manual_retry_lane or {},
    )

    groups = [
        {
            "group": "primary/counterscreen queue",
            "group_signal": _group_signal(primary_rows),
            "rows": primary_rows,
        },
        {
            "group": "watch state",
            "group_signal": _group_signal(watch_rows),
            "rows": watch_rows,
        },
        {
            "group": "precision monitor",
            "group_signal": _group_signal(precision_rows),
            "rows": precision_rows,
        },
        {
            "group": "failure surface",
            "group_signal": _group_signal(failure_rows),
            "rows": failure_rows,
        },
        {
            "group": "retry preset surface",
            "group_signal": _group_signal(retry_rows),
            "rows": retry_rows,
        },
        {
            "group": "hold guard surface",
            "group_signal": _group_signal(hold_rows),
            "rows": hold_rows,
        },
        {
            "group": "validation review surfaces",
            "group_signal": _group_signal(validation_review_rows),
            "rows": validation_review_rows,
        },
        {
            "group": "branch review surfaces",
            "group_signal": _group_signal(krs1_branch_review_rows + dpre1_branch_review_rows),
            "rows": krs1_branch_review_rows + dpre1_branch_review_rows,
        },
        {
            "group": "rescue review surfaces",
            "group_signal": _group_signal(tcruzi_pde_rescue_rows),
            "rows": tcruzi_pde_rescue_rows,
        },
        {
            "group": "manual retry lanes",
            "group_signal": _group_signal(manual_retry_rows),
            "rows": manual_retry_rows,
        },
        {
            "group": "kinase retry templates",
            "group_signal": _group_signal(kinase_template_rows),
            "rows": kinase_template_rows,
        },
        {
            "group": "target retry templates",
            "group_signal": _group_signal(target_retry_template_rows),
            "rows": target_retry_template_rows,
        },
        {
            "group": "stage6 retry templates",
            "group_signal": _group_signal(stage6_retry_template_rows),
            "rows": stage6_retry_template_rows,
        },
        {
            "group": "mapping-fix retry templates",
            "group_signal": _group_signal(mapping_fix_template_rows),
            "rows": mapping_fix_template_rows,
        },
        {
            "group": "stack/handoff/final summary",
            "group_signal": _group_signal(campaign_rows),
            "rows": campaign_rows,
        },
    ]
    if dengue_stage6_rows:
        groups.insert(
            7,
            {
                "group": "dengue stage6 retry family",
                "group_signal": _group_signal(dengue_stage6_rows),
                "rows": dengue_stage6_rows,
            },
        )
    rescue_insert_at = len(groups) - 1
    if hard_target_rescue_lane_rows:
        groups.insert(
            rescue_insert_at,
            {
                "group": "hard-target rescue lane",
                "group_signal": _group_signal(hard_target_rescue_lane_rows),
                "rows": hard_target_rescue_lane_rows,
            },
        )
        rescue_insert_at += 1
    if rescue_anchor_artifacts_rows:
        groups.insert(
            rescue_insert_at,
            {
                "group": "rescue anchor artifacts",
                "group_signal": _group_signal(rescue_anchor_artifacts_rows),
                "rows": rescue_anchor_artifacts_rows,
            },
        )
        rescue_insert_at += 1
    if rescue_three_bead_candidates_rows:
        groups.insert(
            rescue_insert_at,
            {
                "group": "3-bead rescue candidates",
                "group_signal": _group_signal(rescue_three_bead_candidates_rows),
                "rows": rescue_three_bead_candidates_rows,
            },
        )
        rescue_insert_at += 1
    if ligand_admet_rows:
        groups.insert(
            rescue_insert_at,
            {
                "group": "admet/selectivity module",
                "group_signal": _group_signal(ligand_admet_rows),
                "rows": ligand_admet_rows,
            },
        )
        rescue_insert_at += 1
    if allatom_group_rows:
        groups.insert(
            rescue_insert_at,
            {
                "group": "all-atom refinement/rescue family",
                "group_signal": _group_signal(allatom_group_rows),
                "rows": allatom_group_rows,
            },
        )
    rows = [row for group in groups for row in group["rows"]]

    pqs = _summary(primary_queue or {})
    aqs = _summary(antitarget_queue or {})
    pm = _summary(precision_monitor or {})
    primary_focus_target = _text(pm.get("focus_target_id"), pqs.get("first_actionable_target_id"))
    primary_focus_shard = _text(pm.get("focus_shard_id"), pqs.get("first_actionable_shard_id"))
    primary_focus_queue_status = _text(pm.get("focus_queue_status"), pqs.get("first_actionable_queue_status"))
    krs1_branch_review = _summary(tcruzi_krs1_branch_review_surface or {})
    krs1_branch_review_ready = _text(krs1_branch_review.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
    krs1_branch_review_validated = bool(krs1_branch_review.get("branch_validated", False)) or "validated" in _text(
        krs1_branch_review.get("branch_state"),
        krs1_branch_review.get("result_review_status"),
        krs1_branch_review.get("result_summary_status"),
        krs1_branch_review.get("next_required_step"),
    )
    krs1_branch_review_selected = bool(
        krs1_branch_review_ready
        and (
            primary_focus_target == "T. cruzi KRS1"
            or (krs1_branch_review_validated and primary_focus_target == _text(krs1_branch_review.get("successor_target"), "LRRK2"))
            or krs1_branch_review_validated
        )
    )
    selected_krs1_branch_review_next_required_step = _text(krs1_branch_review.get("next_required_step")) if krs1_branch_review_selected else ""
    fs = _summary(failure_surface or {})
    hg = _summary(hold_guard or {})
    lvr = _summary(lbdhodh_gate51_validation_review_surface or {})
    dpre1_branch_review = _summary(dpre1_branch_review_surface or {})
    trr = _summary(tcruzi_pde_rescue_review_surface or {})
    tpr = _summary(tcruzi_pde_promoted_top4_review_packet or {})
    tbr = _summary(tcruzi_pde_rescue_only_branch_summary or {})
    tcruzi_pde_promoted_top4_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                rh,
                ("tcruzi_pde_promoted_top4_review_packet_operator_review_ready",),
            ),
            (tpr, ("packet_ready_for_operator_review", "packet_ready")),
            (
                tbr,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
        ],
        wetlab_gate_specs=[
            (rh, ("tcruzi_pde_promoted_top4_review_packet_wetlab_gate_pass",)),
            (tpr, ("wetlab_gate_pass", "packet_ready")),
            (
                tbr,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
        ],
        final_gate_specs=[
            (rh, ("tcruzi_pde_promoted_top4_review_packet_wetlab_final_gate_pass",)),
            (tpr, ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready")),
            (
                tbr,
                (
                    "review_packet_final_gate_pass",
                    "wetlab_final_gate_pass",
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
        ],
        claim_gate_available_specs=[
            (rh, ("tcruzi_pde_promoted_top4_review_packet_claim_gate_available",)),
            (tpr, ("claim_gate_available",)),
            (tbr, ("review_packet_claim_gate_available", "claim_gate_available")),
        ],
        claim_ready_specs=[
            (rh, ("tcruzi_pde_promoted_top4_review_packet_claim_ready_for_allatom",)),
            (tpr, ("claim_ready_for_allatom",)),
            (tbr, ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom")),
        ],
        default_ready=bool(_text(tpr.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"),
    )
    tcruzi_pde_rescue_only_branch_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (rh, ("tcruzi_pde_rescue_only_branch_summary_operator_review_ready",)),
            (
                tbr,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("packet_ready_for_operator_review", "packet_ready")),
        ],
        wetlab_gate_specs=[
            (rh, ("tcruzi_pde_rescue_only_branch_summary_wetlab_gate_pass",)),
            (
                tbr,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("wetlab_gate_pass", "packet_ready")),
        ],
        final_gate_specs=[
            (rh, ("tcruzi_pde_rescue_only_branch_summary_wetlab_final_gate_pass",)),
            (
                tbr,
                (
                    "review_packet_final_gate_pass",
                    "wetlab_final_gate_pass",
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready")),
        ],
        claim_gate_available_specs=[
            (rh, ("tcruzi_pde_rescue_only_branch_summary_claim_gate_available",)),
            (tbr, ("review_packet_claim_gate_available", "claim_gate_available")),
            (tpr, ("claim_gate_available",)),
        ],
        claim_ready_specs=[
            (rh, ("tcruzi_pde_rescue_only_branch_summary_claim_ready_for_allatom",)),
            (tbr, ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom")),
            (tpr, ("claim_ready_for_allatom",)),
        ],
        default_ready=bool(
            _text(tbr.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
            and bool(tbr.get("promoted_top4_packet_ready", False))
        ),
    )
    selected_rescue_branch_operator_packet_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_ready",
                    "tcruzi_pde_rescue_operator_packet_operator_review_ready",
                    "tcruzi_pde_rescue_operator_packet_ready",
                ),
            )
        ],
        wetlab_gate_specs=[
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_wetlab_gate_pass",
                    "tcruzi_pde_rescue_operator_packet_wetlab_gate_pass",
                ),
            )
        ],
        final_gate_specs=[
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_wetlab_final_gate_pass",
                    "tcruzi_pde_rescue_operator_packet_wetlab_final_gate_pass",
                ),
            )
        ],
        claim_gate_available_specs=[
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_claim_gate_available",
                    "tcruzi_pde_rescue_operator_packet_claim_gate_available",
                ),
            )
        ],
        claim_ready_specs=[
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_claim_ready_for_allatom",
                    "tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom",
                ),
            )
        ],
        default_ready=bool(rh.get("selected_rescue_branch_operator_packet_ready", False)),
    )
    selected_rescue_branch_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (rh, ("selected_rescue_branch_operator_review_ready",)),
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_ready",
                    "tcruzi_pde_rescue_operator_packet_operator_review_ready",
                    "tcruzi_pde_rescue_operator_packet_ready",
                ),
            ),
            (
                tbr,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("packet_ready_for_operator_review", "packet_ready")),
        ],
        wetlab_gate_specs=[
            (rh, ("selected_rescue_branch_wetlab_gate_pass",)),
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_wetlab_gate_pass",
                    "tcruzi_pde_rescue_operator_packet_wetlab_gate_pass",
                ),
            ),
            (
                tbr,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("wetlab_gate_pass", "packet_ready")),
        ],
        final_gate_specs=[
            (rh, ("selected_rescue_branch_wetlab_final_gate_pass",)),
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_wetlab_final_gate_pass",
                    "tcruzi_pde_rescue_operator_packet_wetlab_final_gate_pass",
                ),
            ),
            (
                tbr,
                (
                    "review_packet_final_gate_pass",
                    "wetlab_final_gate_pass",
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tpr, ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready")),
        ],
        claim_gate_available_specs=[
            (rh, ("selected_rescue_branch_claim_gate_available",)),
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_claim_gate_available",
                    "tcruzi_pde_rescue_operator_packet_claim_gate_available",
                ),
            ),
            (tbr, ("review_packet_claim_gate_available", "claim_gate_available")),
            (tpr, ("claim_gate_available",)),
        ],
        claim_ready_specs=[
            (rh, ("selected_rescue_branch_claim_ready_for_allatom",)),
            (
                rh,
                (
                    "selected_rescue_branch_operator_packet_claim_ready_for_allatom",
                    "tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom",
                ),
            ),
            (tbr, ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom")),
            (tpr, ("claim_ready_for_allatom",)),
        ],
        default_ready=bool(
            selected_rescue_branch_operator_packet_gate["packet_ready_for_operator_review"]
            or _text(tbr.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
            or tcruzi_pde_promoted_top4_gate["packet_ready_for_operator_review"]
        ),
    )
    lds = _summary(lbdhodh_stage6_tuning_surface or {})
    ldr = _summary(lbdhodh_exploratory_retry_lane or {})
    smr = _summary(stk17b_manual_retry_lane or {})
    semr = _summary(stk17b_exploratory_retry_lane or {})
    sefr = _summary(stk17b_exploratory_followup_lane or {})
    sfrs = _summary(stk17b_followup_review_surface or {})
    dgs = _summary(dengue_stage6_tuning_surface or {})
    dgr = _summary(dengue_exploratory_retry_lane or {})
    krt = _summary(kinase_retry_policy_templates or {})
    trt = _summary(target_retry_policy_templates or {})
    s6rt = _summary(stage6_retry_template_rows[0] if stage6_retry_template_rows else {})
    pmr = _summary(plpro_manual_retry_lane or {})
    selected_lane_summary = (
        sefr
        if _text(sefr.get("target_id")) == _text(rh.get("selected_manual_retry_target_id"))
        and _lane_shard_display(stk17b_exploratory_followup_lane) == _text(rh.get("selected_manual_retry_shard_id"))
        and _text(sefr.get("selected_command_kind")) == _text(rh.get("selected_manual_retry_selected_command_kind"))
        else semr
        if _text(semr.get("target_id")) == _text(rh.get("selected_manual_retry_target_id"))
        and _text(semr.get("shard_id")) == _text(rh.get("selected_manual_retry_shard_id"))
        and _text(semr.get("selected_command_kind")) == _text(rh.get("selected_manual_retry_selected_command_kind"))
        else smr
        if _text(smr.get("target_id")) == _text(rh.get("selected_manual_retry_target_id"))
        and _text(smr.get("shard_id")) == _text(rh.get("selected_manual_retry_shard_id"))
        and _text(smr.get("selected_command_kind")) == _text(rh.get("selected_manual_retry_selected_command_kind"))
        else pmr
    )
    mfr = _summary(mapping_fix_retry_support or {})
    smfl = _summary(stage1_mapping_fix_lanes or {})
    mfrpt = _summary(mapping_fix_retry_policy_templates or {})
    rescue_lane = _summary(hard_target_rescue_lane or {})
    rescue_anchors = _summary(rescue_anchor_artifacts or {})
    rescue_three_bead = _summary(rescue_three_bead_candidates or {})
    selected_manual_retry_lane = _select_manual_retry_lane(
        retry_handoff_summary or {},
        lbdhodh_exploratory_retry_lane or {},
        stk17b_exploratory_followup_lane or {},
        stk17b_exploratory_retry_lane or {},
        stk17b_manual_retry_lane or {},
        plpro_manual_retry_lane or {},
    )
    selected_manual_retry_lane_payload = _summary(selected_manual_retry_lane)
    selected_lane_summary = selected_manual_retry_lane_payload
    manual_retry_lane_next_step = _manual_retry_next_step(
        retry_handoff_summary or {},
        lbdhodh_exploratory_retry_lane or {},
        stk17b_exploratory_followup_lane or {},
        stk17b_exploratory_retry_lane or {},
        stk17b_manual_retry_lane or {},
        plpro_manual_retry_lane or {},
    )
    stk17b_followup_review_next_step = _stk17b_followup_review_next_step(stk17b_followup_review_surface)
    tcruzi_pde_rescue_review_next_step = _tcruzi_pde_rescue_review_next_step(tcruzi_pde_rescue_review_surface)
    tcruzi_pde_rescue_only_branch_next_step = _tcruzi_pde_rescue_only_branch_next_step(
        tcruzi_pde_rescue_only_branch_summary
    )
    dengue_stage6_queue_priority = _text(pqs.get("first_actionable_target_id")) == "Dengue NS2B-NS3 protease" and bool(
        _text(pqs.get("first_actionable_shard_id"))
    )
    dengue_stage6_next_required_step = _text(
        pqs.get("next_required_step") if dengue_stage6_queue_priority else "",
        dgr.get("next_required_step"),
        dgs.get("next_required_step"),
    )
    dpre1_branch_review_ready = _text(dpre1_branch_review.get("status")) == "wetlab_dpre1_branch_review_surface_ready"
    dpre1_priority_step = _text(
        dpre1_branch_review.get("next_required_step") if dpre1_branch_review_ready else "",
    )
    selected_is_stk17b_followup = bool(
        _text(selected_lane_summary.get("target_id")) == "STK17B (DRAK2)"
        and _text(selected_lane_summary.get("followup_lane_label"), selected_lane_summary.get("lane_label"))
        == "exploratory_gate4.5_followup"
    )
    raw_ps = _summary(partnering_stack or {})
    ps = _partnering_stack_summary(partnering_stack or {})
    mh = _summary(master_handoff_dashboard or {})
    fc = _summary(final_campaign_summary or {})
    mt = _summary(master_terminal_review or {})
    p_loop = _pid_snapshot(DEFAULT_PRIMARY_WATCH_LOOP_PID)
    a_loop = _pid_snapshot(DEFAULT_ANTITARGET_WATCHER_LOOP_PID)
    p_loop_text = _watch_loop_text(p_loop)
    a_loop_text = _watch_loop_text(a_loop)

    return {
        "summary": {
            "status": "wetlab_current_results_index_ready",
            "group_count": len(groups),
            "surface_count": len(rows),
            "primary_queue_first_actionable_target_id": _text(pqs.get("first_actionable_target_id")),
            "primary_queue_first_actionable_shard_id": _text(pqs.get("first_actionable_shard_id")),
            "counter_queue_first_actionable_primary_target_id": _text(aqs.get("first_actionable_primary_target_id")),
            "counter_queue_first_actionable_anti_target_id": _text(aqs.get("first_actionable_anti_target_id")),
            "primary_watch_loop_pid": _safe_int(p_loop.get("pid")),
            "primary_watch_loop_attached": bool(p_loop.get("pid_alive", False)),
            "primary_watch_loop_liveness": p_loop_text.split(" | ")[1].split(" ", 1)[1],
            "primary_watch_loop_fallback_mode": p_loop_text.split(" | ")[2].split(" ", 1)[1],
            "antitarget_watch_loop_pid": _safe_int(a_loop.get("pid")),
            "antitarget_watch_loop_attached": bool(a_loop.get("pid_alive", False)),
            "antitarget_watch_loop_liveness": a_loop_text.split(" | ")[1].split(" ", 1)[1],
            "antitarget_watch_loop_fallback_mode": a_loop_text.split(" | ")[2].split(" ", 1)[1],
            "precision_monitor_completion_pct": _safe_float(pm.get("completion_pct")),
            "precision_monitor_successful_completion_pct": _safe_float(pm.get("successful_completion_pct")),
            "precision_monitor_held_completion_pct": _safe_float(pm.get("held_completion_pct")),
            "failure_surface_auto_hold_row_count": _safe_int(fs.get("auto_hold_row_count")),
            "hold_guard_blocked_target_id": _text(hg.get("guard_blocked_target_id")),
            "hold_guard_streak": _safe_int(hg.get("guard_hold_streak")),
            "hold_guard_limit": _safe_int(hg.get("guard_hold_limit")),
            "primary_focus_target_id": primary_focus_target,
            "primary_focus_shard_id": primary_focus_shard,
            "primary_focus_queue_status": primary_focus_queue_status,
            "krs1_branch_review_ready": krs1_branch_review_ready,
            "krs1_branch_review_target_id": _text(krs1_branch_review.get("target_id")),
            "krs1_branch_review_branch_label": _text(krs1_branch_review.get("branch_label")),
            "krs1_branch_review_branch_state": _text(krs1_branch_review.get("branch_state")),
            "krs1_branch_review_validated": krs1_branch_review_validated,
            "krs1_branch_review_source_priority": _text(krs1_branch_review.get("source_priority")),
            "krs1_branch_review_decision_source_priority": _text(krs1_branch_review.get("decision_source_priority")),
            "krs1_branch_review_stage6_tuning_surface_ready": bool(krs1_branch_review.get("stage6_tuning_surface_ready", False)),
            "krs1_branch_review_stage6_tuning_recommended_threshold_A": _safe_float(
                krs1_branch_review.get("stage6_tuning_recommended_threshold_A")
            ),
            "krs1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
                krs1_branch_review.get("stage6_tuning_immediately_runnable_command_kind")
            ),
            "krs1_branch_review_exploratory_retry_lane_ready": bool(
                krs1_branch_review.get("exploratory_retry_lane_ready", False)
            ),
            "krs1_branch_review_exploratory_source_priority": _text(
                krs1_branch_review.get("exploratory_source_priority")
            ),
            "krs1_branch_review_exploratory_retry_lane_label": _text(
                krs1_branch_review.get("exploratory_retry_lane_label")
            ),
            "krs1_branch_review_exploratory_retry_selected_command_kind": _text(
                krs1_branch_review.get("exploratory_retry_selected_command_kind")
            ),
            "krs1_branch_review_exploratory_retry_selected_threshold_A": _safe_float(
                krs1_branch_review.get("exploratory_retry_selected_threshold_A")
            ),
            "krs1_branch_review_successor_target": _text(krs1_branch_review.get("successor_target")),
            "krs1_branch_review_successor_gate_state": _text(krs1_branch_review.get("successor_gate_state")),
            "krs1_branch_review_next_required_step": _text(krs1_branch_review.get("next_required_step")),
            "selected_krs1_branch_review_target_id": _text(krs1_branch_review.get("target_id")) if krs1_branch_review_selected else "",
            "selected_krs1_branch_review_surface_label": "krs1_branch_review_surface" if krs1_branch_review_selected else "",
            "selected_krs1_branch_review_branch_label": _text(krs1_branch_review.get("branch_label")) if krs1_branch_review_selected else "",
            "selected_krs1_branch_review_branch_state": _text(krs1_branch_review.get("branch_state")) if krs1_branch_review_selected else "",
            "selected_krs1_branch_review_selected_command_kind": _text(
                krs1_branch_review.get("exploratory_retry_selected_command_kind")
            )
            if krs1_branch_review_selected
            else "",
            "selected_krs1_branch_review_selected_threshold_A": _safe_float(
                krs1_branch_review.get("exploratory_retry_selected_threshold_A"), 0.0
            )
            if krs1_branch_review_selected
            else 0.0,
            "selected_krs1_branch_review_next_required_step": selected_krs1_branch_review_next_required_step,
            "lbdhodh_gate51_validation_review_ready": bool(_text(lvr.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready"),
            "lbdhodh_gate51_validation_review_target_id": _text(lvr.get("target_id")),
            "lbdhodh_gate51_validation_review_decision": _text(lvr.get("decision")),
            "lbdhodh_gate51_validation_review_default_lane_reopen_allowed": bool(lvr.get("default_lane_reopen_allowed", False)),
            "lbdhodh_gate51_validation_review_branch_to_gate51_only": bool(lvr.get("branch_to_gate51_only", False)),
            "lbdhodh_gate51_validation_review_success_count": _safe_int(lvr.get("gate51_validation_success_count")),
            "lbdhodh_gate51_validation_review_row_count": _safe_int(lvr.get("gate51_validation_row_count")),
            "lbdhodh_gate51_validation_review_validated_command_kind": _text(lvr.get("validated_command_kind")),
            "lbdhodh_gate51_validation_review_validated_threshold_A": _safe_float(lvr.get("validated_threshold_A")),
            "lbdhodh_gate51_validation_review_next_required_step": _text(lvr.get("next_required_step")),
            "dpre1_branch_review_ready": dpre1_branch_review_ready,
            "dpre1_branch_review_target_id": _text(dpre1_branch_review.get("target_id")),
            "dpre1_branch_review_branch_label": _text(dpre1_branch_review.get("branch_label")),
            "dpre1_branch_review_branch_state": _text(dpre1_branch_review.get("branch_state")),
            "dpre1_branch_review_source_priority": _text(dpre1_branch_review.get("source_priority")),
            "dpre1_branch_review_result_review_status": _text(dpre1_branch_review.get("result_review_status")),
            "dpre1_branch_review_result_summary_status": _text(dpre1_branch_review.get("result_summary_status")),
            "dpre1_branch_review_launch_packet_status": _text(dpre1_branch_review.get("launch_packet_status")),
            "dpre1_branch_review_stage6_tuning_surface_ready": bool(dpre1_branch_review.get("stage6_tuning_surface_ready", False)),
            "dpre1_branch_review_stage6_tuning_source_priority": _text(dpre1_branch_review.get("stage6_tuning_source_priority")),
            "dpre1_branch_review_stage6_tuning_recommended_threshold_A": _safe_float(
                dpre1_branch_review.get("stage6_tuning_recommended_threshold_A")
            ),
            "dpre1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
                dpre1_branch_review.get("stage6_tuning_immediately_runnable_command_kind")
            ),
            "dpre1_branch_review_exploratory_retry_lane_ready": bool(
                dpre1_branch_review.get("exploratory_retry_lane_ready", False)
            ),
            "dpre1_branch_review_exploratory_source_priority": _text(dpre1_branch_review.get("exploratory_source_priority")),
            "dpre1_branch_review_exploratory_retry_lane_label": _text(dpre1_branch_review.get("exploratory_retry_lane_label")),
            "dpre1_branch_review_exploratory_retry_selected_command_kind": _text(
                dpre1_branch_review.get("exploratory_retry_selected_command_kind")
            ),
            "dpre1_branch_review_exploratory_retry_selected_threshold_A": _safe_float(
                dpre1_branch_review.get("exploratory_retry_selected_threshold_A")
            ),
            "dpre1_branch_review_successor_target": _text(dpre1_branch_review.get("successor_target")),
            "dpre1_branch_review_successor_gate_state": _text(dpre1_branch_review.get("successor_gate_state")),
            "dpre1_branch_review_next_required_step": _text(dpre1_branch_review.get("next_required_step")),
            "tcruzi_pde_rescue_review_ready": bool(_text(trr.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready"),
            "tcruzi_pde_rescue_review_target_id": _text(trr.get("target_id")),
            "tcruzi_pde_rescue_review_decision": _text(trr.get("decision")),
            "tcruzi_pde_rescue_review_default_lane_reopen_allowed": bool(trr.get("default_lane_reopen_allowed", False)),
            "tcruzi_pde_rescue_review_branch_to_rescue_only": bool(trr.get("branch_to_rescue_only", False)),
            "tcruzi_pde_rescue_review_promoted_candidate_count": _safe_int(trr.get("promoted_candidate_count")),
            "tcruzi_pde_rescue_review_under_2p5_candidate_count": _safe_int(trr.get("under_2p5_candidate_count")),
            "tcruzi_pde_rescue_review_near_candidate_count": _safe_int(trr.get("near_candidate_count")),
            "tcruzi_pde_rescue_review_selected_command_kind": _text(trr.get("selected_command_kind")),
            "tcruzi_pde_rescue_review_selected_threshold_A": _safe_float(trr.get("selected_threshold_A")),
            "tcruzi_pde_rescue_review_next_required_step": _text(trr.get("next_required_step")),
            "tcruzi_pde_promoted_top4_review_packet_ready": bool(
                _text(tpr.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
            ),
            "tcruzi_pde_promoted_top4_review_packet_operator_review_ready": tcruzi_pde_promoted_top4_gate[
                "packet_ready_for_operator_review"
            ],
            "tcruzi_pde_promoted_top4_review_packet_wetlab_gate_pass": tcruzi_pde_promoted_top4_gate[
                "wetlab_gate_pass"
            ],
            "tcruzi_pde_promoted_top4_review_packet_wetlab_final_gate_pass": tcruzi_pde_promoted_top4_gate[
                "wetlab_final_gate_pass"
            ],
            "tcruzi_pde_promoted_top4_review_packet_claim_gate_available": tcruzi_pde_promoted_top4_gate[
                "claim_gate_available"
            ],
            "tcruzi_pde_promoted_top4_review_packet_claim_ready_for_allatom": tcruzi_pde_promoted_top4_gate[
                "claim_ready_for_allatom"
            ],
            "tcruzi_pde_promoted_top4_review_packet_target_id": _text(tpr.get("target_id")),
            "tcruzi_pde_promoted_top4_review_packet_shard_id": _text(tpr.get("shard_id")),
            "tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count": _safe_int(
                tpr.get("promoted_candidate_count")
            ),
            "tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count": _safe_int(
                tpr.get("under_2p5_candidate_count")
            ),
            "tcruzi_pde_promoted_top4_review_packet_selected_command_kind": _text(
                tpr.get("selected_command_kind")
            ),
            "tcruzi_pde_promoted_top4_review_packet_strict_threshold_A": _safe_float(
                tpr.get("strict_threshold_A")
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_ligand_id": _text(tpr.get("best_ligand_id")),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name": _text(
                tpr.get("best_compound_name_human_readable"),
                tpr.get("best_compound_name"),
                tpr.get("best_ligand_id"),
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable": _text(
                tpr.get("best_compound_name_human_readable")
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution": _text(
                tpr.get("best_compound_name_resolution"), default="unresolved"
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A": _safe_float(
                tpr.get("best_mean_min_distance_A")
            ),
            "tcruzi_pde_promoted_top4_review_packet_next_required_step": _text(tpr.get("next_required_step")),
            "tcruzi_pde_rescue_only_branch_summary_ready": bool(
                _text(tbr.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
            ),
            "tcruzi_pde_rescue_only_branch_summary_operator_review_ready": tcruzi_pde_rescue_only_branch_gate[
                "packet_ready_for_operator_review"
            ],
            "tcruzi_pde_rescue_only_branch_summary_wetlab_gate_pass": tcruzi_pde_rescue_only_branch_gate[
                "wetlab_gate_pass"
            ],
            "tcruzi_pde_rescue_only_branch_summary_wetlab_final_gate_pass": tcruzi_pde_rescue_only_branch_gate[
                "wetlab_final_gate_pass"
            ],
            "tcruzi_pde_rescue_only_branch_summary_claim_gate_available": tcruzi_pde_rescue_only_branch_gate[
                "claim_gate_available"
            ],
            "tcruzi_pde_rescue_only_branch_summary_claim_ready_for_allatom": tcruzi_pde_rescue_only_branch_gate[
                "claim_ready_for_allatom"
            ],
            "tcruzi_pde_rescue_only_branch_summary_target_id": _text(tbr.get("target_id")),
            "tcruzi_pde_rescue_only_branch_summary_shard_id": _text(tbr.get("shard_id")),
            "tcruzi_pde_rescue_only_branch_summary_branch_state": _text(tbr.get("branch_state")),
            "tcruzi_pde_rescue_only_branch_summary_default_lane_reopen_allowed": bool(
                tbr.get("default_lane_reopen_allowed", False)
            ),
            "tcruzi_pde_rescue_only_branch_summary_branch_to_rescue_only": bool(
                tbr.get("branch_to_rescue_only", False)
            ),
            "tcruzi_pde_rescue_only_branch_summary_selected_command_kind": _text(
                tbr.get("selected_command_kind")
            ),
            "tcruzi_pde_rescue_only_branch_summary_selected_threshold_A": _safe_float(
                tbr.get("selected_threshold_A")
            ),
            "tcruzi_pde_rescue_only_branch_summary_promoted_top4_packet_ready": bool(
                tbr.get("promoted_top4_packet_ready", False)
            ),
            "tcruzi_pde_rescue_only_branch_summary_promoted_candidate_count": _safe_int(
                tbr.get("promoted_candidate_count")
            ),
            "tcruzi_pde_rescue_only_branch_summary_under_2p5_candidate_count": _safe_int(
                tbr.get("under_2p5_candidate_count")
            ),
            "tcruzi_pde_rescue_only_branch_summary_best_ligand_id": _text(tbr.get("best_ligand_id")),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name": _text(
                tbr.get("best_compound_name_human_readable"),
                tbr.get("best_compound_name"),
                tbr.get("best_ligand_id"),
            ),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name_human_readable": _text(
                tbr.get("best_compound_name_human_readable")
            ),
            "tcruzi_pde_rescue_only_branch_summary_best_compound_name_resolution": _text(
                tbr.get("best_compound_name_resolution"), default="unresolved"
            ),
            "tcruzi_pde_rescue_only_branch_summary_best_mean_min_distance_A": _safe_float(
                tbr.get("best_mean_min_distance_A")
            ),
            "tcruzi_pde_rescue_only_branch_summary_next_required_step": _text(
                tbr.get("next_required_step")
            ),
            "lbdhodh_stage6_tuning_ready": bool(_text(lds.get("status")) == "wetlab_lbdhodh_stage6_tuning_surface_ready"),
            "lbdhodh_stage6_recommended_threshold_A": _safe_float(lds.get("recommended_observed_threshold_A")),
            "lbdhodh_retry_lane_ready": bool(_text(ldr.get("status")) == "wetlab_lbdhodh_exploratory_retry_lane_ready"),
            "lbdhodh_retry_target_id": _text(ldr.get("target_id")),
            "lbdhodh_retry_shard_id": _text(ldr.get("shard_id")),
            "lbdhodh_retry_selected_command_kind": _text(ldr.get("selected_command_kind")),
            "dengue_stage6_tuning_ready": bool(_text(dgs.get("status")) == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"),
            "dengue_stage6_recommended_threshold_A": _safe_float(dgs.get("recommended_observed_threshold_A")),
            "dengue_stage6_immediately_runnable_command_kind": _text(dgs.get("immediately_runnable_command_kind")),
            "dengue_stage6_retry_lane_ready": bool(_text(dgr.get("status")) == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"),
            "dengue_stage6_retry_ready_for_manual_retry": bool(dgr.get("ready_for_manual_retry", False)),
            "dengue_stage6_retry_source_priority": "execution_queue" if dengue_stage6_queue_priority else "exploratory_lane" if bool(dgr.get("status")) else "tuning_surface",
            "dengue_stage6_retry_target_id": _text(
                pqs.get("first_actionable_target_id") if dengue_stage6_queue_priority else "",
                dgr.get("target_id"),
                dgs.get("target_id"),
            ),
            "dengue_stage6_retry_shard_id": _text(
                pqs.get("first_actionable_shard_id") if dengue_stage6_queue_priority else "",
                dgr.get("shard_id"),
                dgs.get("next_retry_shard_id"),
            ),
            "dengue_stage6_retry_selected_command_kind": _text(
                dgr.get("selected_command_kind"),
                dgs.get("immediately_runnable_command_kind"),
            ),
            "dengue_stage6_retry_lane_label": _text(dgr.get("lane_label"), "dengue_stage6_tuned_retry"),
            "dengue_stage6_retry_next_required_step": dengue_stage6_next_required_step,
            "stk17b_manual_retry_target_id": _text(smr.get("target_id")),
            "stk17b_manual_retry_shard_id": _text(smr.get("shard_id")),
            "stk17b_manual_retry_selected_command_kind": _text(smr.get("selected_command_kind")),
            "stk17b_exploratory_retry_target_id": _text(semr.get("target_id")),
            "stk17b_exploratory_retry_shard_id": _text(semr.get("shard_id")),
            "stk17b_exploratory_retry_selected_command_kind": _text(semr.get("selected_command_kind")),
            "stk17b_exploratory_followup_target_id": _text(sefr.get("target_id")),
            "stk17b_exploratory_followup_shard_id": _lane_shard_display(stk17b_exploratory_followup_lane),
            "stk17b_exploratory_followup_selected_command_kind": _text(sefr.get("selected_command_kind")),
            "stk17b_exploratory_followup_lane_label": _text(sefr.get("followup_lane_label"), sefr.get("lane_label")),
            "stk17b_exploratory_followup_freeze_state": _text(sefr.get("freeze_state"), sefr.get("hard_freeze_state")),
            "stk17b_exploratory_followup_freeze_note": _text(sefr.get("freeze_note")),
            "stk17b_exploratory_followup_followup_shard_ids": _text(sefr.get("followup_shard_ids")),
            "kinase_retry_policy_templates_ready": bool(_text(krt.get("status")) == "wetlab_kinase_retry_policy_templates_ready"),
            "kinase_retry_template_target_count": _safe_int(krt.get("template_target_count")),
            "kinase_retry_empirical_validated_target_count": _safe_int(krt.get("empirical_validated_target_count")),
            "kinase_retry_gate45_only_target_count": _safe_int(krt.get("gate45_only_target_count")),
            "kinase_retry_guarded_gate55_candidate_target_count": _safe_int(krt.get("guarded_gate55_candidate_target_count")),
            "kinase_retry_focus_target_id": _text(krt.get("focus_target_id")),
            "kinase_retry_focus_template_label": _text(krt.get("focus_template_label")),
            "kinase_retry_focus_selected_command_kind": _text(krt.get("focus_selected_command_kind")),
            "target_retry_policy_templates_ready": bool(_text(trt.get("status")) == "wetlab_target_retry_policy_templates_ready"),
            "target_retry_template_target_count": _safe_int(trt.get("template_target_count")),
            "target_retry_empirical_validated_target_count": _safe_int(trt.get("empirical_validated_target_count")),
            "target_retry_focus_target_id": _text(trt.get("focus_target_id")),
            "target_retry_focus_template_label": _text(trt.get("focus_template_label")),
            "target_retry_focus_selected_command_kind": _text(trt.get("focus_selected_command_kind")),
            "target_retry_focus_selected_threshold_A": _safe_float(trt.get("focus_selected_threshold_A")),
            "stage6_retry_policy_templates_ready": bool(_text(s6rt.get("status")) == "wetlab_target_retry_policy_templates_ready" and bool(stage6_retry_template_rows)),
            "stage6_retry_template_target_count": _safe_int(len(stage6_retry_template_rows)),
            "stage6_retry_gate45_candidate_target_count": _safe_int(
                sum(1 for row in stage6_retry_template_rows if "gate45" in _text(row.get("selected_command_kind")))
            ),
            "stage6_retry_gate51_candidate_target_count": _safe_int(
                sum(1 for row in stage6_retry_template_rows if "gate51" in _text(row.get("selected_command_kind")))
            ),
            "stage6_retry_ready_targets": _text(
                "; ".join(_text(row.get("target_id")) for row in stage6_retry_template_rows if _text(row.get("target_id")))
            ),
            "stage6_retry_gate45_targets": _text(
                "; ".join(
                    _text(row.get("target_id"))
                    for row in stage6_retry_template_rows
                    if "gate45" in _text(row.get("selected_command_kind")) and _text(row.get("target_id"))
                )
            ),
            "stage6_retry_gate51_targets": _text(
                "; ".join(
                    _text(row.get("target_id"))
                    for row in stage6_retry_template_rows
                    if "gate51" in _text(row.get("selected_command_kind")) and _text(row.get("target_id"))
                )
            ),
            "stage6_retry_focus_target_id": _text(
                s6rt.get("target_id"),
                _text(stage6_retry_template_rows[0].get("target_id")) if stage6_retry_template_rows else "",
            ),
            "stage6_retry_focus_template_label": _text(
                s6rt.get("template_label"),
                _text(stage6_retry_template_rows[0].get("template_label")) if stage6_retry_template_rows else "",
            ),
            "stage6_retry_focus_selected_command_kind": _text(
                s6rt.get("selected_command_kind"),
                _text(stage6_retry_template_rows[0].get("selected_command_kind")) if stage6_retry_template_rows else "",
            ),
            "stage6_retry_focus_selected_threshold_A": _safe_float(
                s6rt.get("selected_threshold_A"),
                _safe_float(stage6_retry_template_rows[0].get("selected_threshold_A"), 0.0) if stage6_retry_template_rows else 0.0,
            ),
            "stage6_retry_next_required_step": _text(
                s6rt.get("next_required_step"),
                _text(stage6_retry_template_rows[0].get("next_required_step")) if stage6_retry_template_rows else "",
            ),
            "stage6_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "stk17b_followup_lane_label": _text(sefr.get("followup_lane_label"), sefr.get("lane_label")),
            "stk17b_followup_freeze_state": _text(sefr.get("freeze_state"), sefr.get("hard_freeze_state")),
            "stk17b_followup_freeze_note": _text(sefr.get("freeze_note")),
            "stk17b_followup_followup_shard_ids": _text(sefr.get("followup_shard_ids")),
            "stk17b_followup_review_decision": _text(sfrs.get("decision")),
            "stk17b_followup_review_decision_rationale": _text(sfrs.get("decision_rationale")),
            "stk17b_followup_review_next_required_step": stk17b_followup_review_next_step,
            "selected_manual_retry_target_id": _text(rh.get("selected_manual_retry_target_id")),
            "selected_validated_target_id": _text(rh.get("selected_validated_target_id"), lvr.get("target_id") if bool(lvr.get("gate51_validated", False)) else ""),
            "selected_validated_surface_label": _text(rh.get("selected_validated_surface_label"), "gate5.1_validation_review" if bool(lvr.get("gate51_validated", False)) else ""),
            "selected_validated_selected_command_kind": _text(rh.get("selected_validated_selected_command_kind"), lvr.get("validated_command_kind")),
            "selected_validated_threshold_A": _safe_float(rh.get("selected_validated_threshold_A"), _safe_float(lvr.get("validated_threshold_A"))),
            "selected_validated_next_required_step": _text(rh.get("selected_validated_next_required_step"), lvr.get("next_required_step")),
            "selected_rescue_review_target_id": _text(rh.get("selected_rescue_review_target_id"), trr.get("target_id")),
            "selected_rescue_review_surface_label": _text(
                rh.get("selected_rescue_review_surface_label"),
                "pde_rescue_review" if _text(trr.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready" else "",
            ),
            "selected_rescue_review_selected_command_kind": _text(
                rh.get("selected_rescue_review_selected_command_kind"),
                trr.get("selected_command_kind"),
            ),
            "selected_rescue_review_best_compound_name": _text(
                rh.get("selected_rescue_review_best_compound_name"),
                trr.get("best_compound_name_human_readable"),
                trr.get("best_compound_name"),
                tpr.get("best_compound_name_human_readable"),
                tpr.get("best_compound_name"),
                tpr.get("best_ligand_id"),
            ),
            "selected_rescue_review_best_compound_name_human_readable": _text(
                rh.get("selected_rescue_review_best_compound_name_human_readable"),
                trr.get("best_compound_name_human_readable"),
                tpr.get("best_compound_name_human_readable"),
            ),
            "selected_rescue_review_best_compound_name_resolution": _text(
                rh.get("selected_rescue_review_best_compound_name_resolution"),
                trr.get("best_compound_name_resolution"),
                tpr.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "selected_rescue_review_strict_threshold_A": _safe_float(
                rh.get("selected_rescue_review_strict_threshold_A"),
                _safe_float(trr.get("strict_threshold_A")),
            ),
            "selected_rescue_review_near_threshold_A": _safe_float(
                rh.get("selected_rescue_review_near_threshold_A"),
                _safe_float(trr.get("near_threshold_A")),
            ),
            "selected_rescue_review_promoted_candidate_count": _safe_int(
                rh.get("selected_rescue_review_promoted_candidate_count"),
                _safe_int(trr.get("promoted_candidate_count")),
            ),
            "selected_rescue_review_under_2p5_candidate_count": _safe_int(
                rh.get("selected_rescue_review_under_2p5_candidate_count"),
                _safe_int(trr.get("under_2p5_candidate_count")),
            ),
            "selected_rescue_review_next_required_step": _text(
                tcruzi_pde_rescue_only_branch_next_step,
                rh.get("selected_rescue_review_next_required_step"),
                trr.get("next_required_step"),
            ),
            "selected_rescue_branch_target_id": _text(
                rh.get("selected_rescue_branch_target_id"),
                tbr.get("target_id"),
                tpr.get("target_id"),
                trr.get("target_id"),
            ),
            "selected_rescue_branch_surface_label": _text(
                rh.get("selected_rescue_branch_surface_label"),
                "pde_rescue_only_branch"
                if _text(tbr.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
                else "",
                "pde_promoted_top4_review_packet"
                if _text(tpr.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
                else "",
            ),
            "selected_rescue_branch_shard_id": _text(
                tbr.get("shard_id"),
                tpr.get("shard_id"),
            ),
            "selected_rescue_branch_selected_command_kind": _text(
                rh.get("selected_rescue_branch_selected_command_kind"),
                tbr.get("selected_command_kind"),
                tpr.get("selected_command_kind"),
            ),
            "selected_rescue_branch_best_compound_name": _text(
                rh.get("selected_rescue_branch_best_compound_name"),
                tbr.get("best_compound_name_human_readable"),
                tbr.get("best_compound_name"),
                tpr.get("best_compound_name_human_readable"),
                tpr.get("best_compound_name"),
                tpr.get("best_ligand_id"),
            ),
            "selected_rescue_branch_best_compound_name_human_readable": _text(
                rh.get("selected_rescue_branch_best_compound_name_human_readable"),
                tbr.get("best_compound_name_human_readable"),
                tpr.get("best_compound_name_human_readable"),
            ),
            "selected_rescue_branch_best_compound_name_resolution": _text(
                rh.get("selected_rescue_branch_best_compound_name_resolution"),
                tbr.get("best_compound_name_resolution"),
                tpr.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "selected_rescue_branch_selected_threshold_A": _safe_float(
                rh.get("selected_rescue_branch_selected_threshold_A")
                if rh.get("selected_rescue_branch_selected_threshold_A") not in {"", None}
                else tbr.get("selected_threshold_A")
                if tbr.get("selected_threshold_A") not in {"", None}
                else tpr.get("strict_threshold_A")
            ),
            "selected_rescue_branch_promoted_candidate_count": _safe_int(
                tbr.get("promoted_candidate_count"),
                _safe_int(tpr.get("promoted_candidate_count")),
            ),
            "selected_rescue_branch_under_2p5_candidate_count": _safe_int(
                tbr.get("under_2p5_candidate_count"),
                _safe_int(tpr.get("under_2p5_candidate_count")),
            ),
            "selected_rescue_branch_operator_review_ready": selected_rescue_branch_gate[
                "packet_ready_for_operator_review"
            ],
            "selected_rescue_branch_wetlab_gate_pass": selected_rescue_branch_gate["wetlab_gate_pass"],
            "selected_rescue_branch_wetlab_final_gate_pass": selected_rescue_branch_gate[
                "wetlab_final_gate_pass"
            ],
            "selected_rescue_branch_claim_gate_available": selected_rescue_branch_gate[
                "claim_gate_available"
            ],
            "selected_rescue_branch_claim_ready_for_allatom": selected_rescue_branch_gate[
                "claim_ready_for_allatom"
            ],
            "selected_rescue_branch_operator_packet_ready": selected_rescue_branch_operator_packet_gate[
                "packet_ready_for_operator_review"
            ],
            "selected_rescue_branch_operator_packet_wetlab_gate_pass": selected_rescue_branch_operator_packet_gate[
                "wetlab_gate_pass"
            ],
            "selected_rescue_branch_operator_packet_wetlab_final_gate_pass": selected_rescue_branch_operator_packet_gate[
                "wetlab_final_gate_pass"
            ],
            "selected_rescue_branch_operator_packet_claim_gate_available": selected_rescue_branch_operator_packet_gate[
                "claim_gate_available"
            ],
            "selected_rescue_branch_operator_packet_claim_ready_for_allatom": selected_rescue_branch_operator_packet_gate[
                "claim_ready_for_allatom"
            ],
            "selected_rescue_branch_operator_packet_scope": _text(
                rh.get("selected_rescue_branch_operator_packet_scope")
            ),
            "allatom_family_ready": bool(allatom_family_summary.get("ready", False)),
            "allatom_family_target_count": _safe_int(allatom_family_summary.get("target_count"), 0),
            "allatom_family_surface_count": _safe_int(allatom_family_summary.get("surface_count"), 0),
            "allatom_family_focus_target_id": _text(allatom_family_summary.get("focus_target_id")),
            "allatom_family_focus_surface_label": _text(allatom_family_summary.get("focus_surface_label")),
            "allatom_family_focus_status_line": _text(allatom_family_summary.get("focus_status_line")),
            "allatom_family_focus_commercial_reported_v1": bool(
                allatom_family_summary.get("focus_commercial_reported_v1", False)
            ),
            "allatom_family_focus_commercial_schema_version": _text(
                allatom_family_summary.get("focus_commercial_schema_version")
            ),
            "allatom_family_focus_commercial_hard_gate_pass_v1": bool(
                allatom_family_summary.get("focus_commercial_hard_gate_pass_v1", False)
            ),
            "allatom_family_focus_commercial_overall_score_v1": _safe_float(
                allatom_family_summary.get("focus_commercial_overall_score_v1"),
                0.0,
            ),
            "allatom_family_focus_commercial_risk_bucket_v1": _text(
                allatom_family_summary.get("focus_commercial_risk_bucket_v1")
            ),
            "allatom_family_focus_commercial_decision_class_v1": _text(
                allatom_family_summary.get("focus_commercial_decision_class_v1")
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_v1": list(
                allatom_family_summary.get("focus_commercial_primary_upgrade_actions_v1", []) or []
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_text_v1": _text(
                allatom_family_summary.get("focus_commercial_primary_upgrade_actions_text_v1")
            ),
            "allatom_family_focus_commercial_reported_v2": bool(
                allatom_family_summary.get("focus_commercial_reported_v2", False)
            ),
            "allatom_family_focus_commercial_schema_version_v2": _text(
                allatom_family_summary.get("focus_commercial_schema_version_v2")
            ),
            "allatom_family_focus_commercial_hard_gate_pass_v2": bool(
                allatom_family_summary.get("focus_commercial_hard_gate_pass_v2", False)
            ),
            "allatom_family_focus_commercial_soft_score_v2": _safe_float(
                allatom_family_summary.get("focus_commercial_soft_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_confidence_score_v2": _safe_float(
                allatom_family_summary.get("focus_commercial_confidence_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_overall_score_v2": _safe_float(
                allatom_family_summary.get("focus_commercial_overall_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_risk_bucket_v2": _text(
                allatom_family_summary.get("focus_commercial_risk_bucket_v2")
            ),
            "allatom_family_focus_commercial_decision_class_v2": _text(
                allatom_family_summary.get("focus_commercial_decision_class_v2")
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_v2": list(
                allatom_family_summary.get("focus_commercial_primary_upgrade_actions_v2", []) or []
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_text_v2": _text(
                allatom_family_summary.get("focus_commercial_primary_upgrade_actions_text_v2")
            ),
            "allatom_family_focus_commercial_human_summary_v2": _text(
                allatom_family_summary.get("focus_commercial_human_summary_v2")
            ),
            "allatom_family_focus_translation_gate_version": _text(
                allatom_family_summary.get("focus_translation_gate_version")
            ),
            "allatom_family_focus_translation_gate_focus_status": _text(
                allatom_family_summary.get("focus_translation_gate_focus_status")
            ),
            "allatom_family_focus_translation_gate_focus_score": _safe_float(
                allatom_family_summary.get("focus_translation_gate_focus_score"),
                0.0,
            ),
            "allatom_family_focus_translation_gate_focus_reason": _text(
                allatom_family_summary.get("focus_translation_gate_focus_reason")
            ),
            "allatom_family_focus_pose_validation_reported": bool(
                allatom_family_summary.get("focus_pose_validation_reported", False)
            ),
            "allatom_family_focus_pose_validation_version": _text(
                allatom_family_summary.get("focus_pose_validation_version")
            ),
            "allatom_family_focus_pose_validation_source": _text(
                allatom_family_summary.get("focus_pose_validation_source")
            ),
            "allatom_family_focus_pose_validation_status": _text(
                allatom_family_summary.get("focus_pose_validation_focus_status")
            ),
            "allatom_family_focus_pose_validation_soft_status": _text(
                allatom_family_summary.get("focus_pose_validation_focus_soft_status")
            ),
            "allatom_family_focus_pose_validation_score": _safe_float(
                allatom_family_summary.get("focus_pose_validation_focus_score"),
                0.0,
            ),
            "allatom_family_focus_pose_validation_pass": bool(
                allatom_family_summary.get("focus_pose_validation_focus_pass", False)
            ),
            "allatom_family_focus_pose_validation_pose_preservation_rmsd_A": (
                allatom_family_summary.get("focus_pose_validation_focus_pose_preservation_rmsd_A")
            ),
            "allatom_family_focus_pose_validation_backmapping_consistency_score": (
                allatom_family_summary.get(
                    "focus_pose_validation_focus_backmapping_consistency_score"
                )
            ),
            "allatom_family_focus_pose_validation_thresholds": dict(
                allatom_family_summary.get("focus_pose_validation_focus_thresholds", {}) or {}
            ),
            "allatom_family_focus_pose_validation_failed_checks": list(
                allatom_family_summary.get("focus_pose_validation_focus_failed_checks", []) or []
            ),
            "allatom_family_focus_pose_validation_missing_checks": list(
                allatom_family_summary.get("focus_pose_validation_focus_missing_checks", []) or []
            ),
            "allatom_family_focus_pose_validation_passed_checks": list(
                allatom_family_summary.get("focus_pose_validation_focus_passed_checks", []) or []
            ),
            "allatom_family_focus_pose_validation_action_codes": list(
                allatom_family_summary.get("focus_pose_validation_focus_action_codes", []) or []
            ),
            "allatom_family_focus_pose_validation_blocker_codes": list(
                allatom_family_summary.get("focus_pose_validation_focus_blocker_codes", []) or []
            ),
            "allatom_family_focus_pose_validation_reason": _text(
                allatom_family_summary.get("focus_pose_validation_focus_reason")
            ),
            "allatom_family_focus_shortlist_tier": _text(
                allatom_family_summary.get("focus_shortlist_tier")
            ),
            "allatom_family_focus_recommended_next_expensive_lane": _text(
                allatom_family_summary.get("focus_recommended_next_expensive_lane")
            ),
            "allatom_family_focus_recommended_next_expensive_lane_reason": _text(
                allatom_family_summary.get("focus_recommended_next_expensive_lane_reason")
            ),
            "allatom_family_next_required_step": _text(allatom_family_summary.get("next_required_step")),
            "selected_allatom_focus_available": bool(selected_allatom_focus_context.get("focus_available", False)),
            "selected_allatom_focus_artifact": _text(selected_allatom_focus_context.get("artifact")),
            "selected_allatom_focus_status": _text(selected_allatom_focus_context.get("status")),
            "selected_allatom_readiness_source_surface": _text(
                selected_allatom_focus_context.get("readiness_source_surface")
            ),
            "selected_allatom_readiness_source_artifact": _text(
                selected_allatom_focus_context.get("readiness_source_artifact")
            ),
            "selected_allatom_readiness_semantics": _text(
                selected_allatom_focus_context.get("readiness_semantics")
            ),
            "selected_allatom_operator_review_ready_reported": bool(
                dict(selected_allatom_focus_context.get("reported", {}) or {}).get(
                    "packet_ready_for_operator_review",
                    False,
                )
            ),
            "selected_allatom_operator_review_ready": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "packet_ready_for_operator_review",
                    False,
                )
            ),
            "selected_allatom_wetlab_gate_reported": bool(
                dict(selected_allatom_focus_context.get("reported", {}) or {}).get(
                    "wetlab_gate_pass",
                    False,
                )
            ),
            "selected_allatom_wetlab_gate_pass": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "wetlab_gate_pass",
                    False,
                )
            ),
            "selected_allatom_final_gate_reported": bool(
                dict(selected_allatom_focus_context.get("reported", {}) or {}).get(
                    "wetlab_final_gate_pass",
                    False,
                )
            ),
            "selected_allatom_final_gate_pass": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "wetlab_final_gate_pass",
                    False,
                )
            ),
            "selected_allatom_final_wetlab_ready": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "wetlab_final_gate_pass",
                    False,
                )
            ),
            "selected_allatom_claim_gate_available_reported": bool(
                dict(selected_allatom_focus_context.get("reported", {}) or {}).get(
                    "claim_gate_available",
                    False,
                )
            ),
            "selected_allatom_claim_gate_available": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "claim_gate_available",
                    False,
                )
            ),
            "selected_allatom_claim_ready_for_allatom_reported": bool(
                dict(selected_allatom_focus_context.get("reported", {}) or {}).get(
                    "claim_ready_for_allatom",
                    False,
                )
            ),
            "selected_allatom_claim_ready_for_allatom": bool(
                dict(selected_allatom_focus_context.get("snapshot", {}) or {}).get(
                    "claim_ready_for_allatom",
                    False,
                )
            ),
            "selected_allatom_target_id": _text(selected_allatom_focus_context.get("target_id")),
            "selected_allatom_surface_label": _text(selected_allatom_focus_context.get("surface_label")),
            "selected_allatom_selected_command_kind": _text(
                selected_allatom_focus_context.get("selected_command_kind")
            ),
            "selected_allatom_selected_threshold_A": _safe_float(
                selected_allatom_focus_context.get("selected_threshold_A"),
                0.0,
            ),
            "selected_allatom_packet_scope": _text(selected_allatom_focus_context.get("packet_scope")),
            "selected_allatom_best_compound_name": _text(
                selected_allatom_focus_context.get("best_compound_name")
            ),
            "selected_allatom_best_compound_name_human_readable": _text(
                selected_allatom_focus_context.get("best_compound_name_human_readable")
            ),
            "selected_allatom_best_compound_name_resolution": _text(
                selected_allatom_focus_context.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "selected_allatom_best_mean_min_distance_A": _safe_float(
                selected_allatom_focus_context.get("best_mean_min_distance_A"),
                0.0,
            ),
            "selected_allatom_best_mean_min_distance_A_source": _text(
                selected_allatom_focus_context.get("best_mean_min_distance_A_source")
            ),
            "selected_allatom_promoted_candidate_count": _safe_int(
                selected_allatom_focus_context.get("promoted_candidate_count"),
                0,
            ),
            "selected_allatom_under_2p5_candidate_count": _safe_int(
                selected_allatom_focus_context.get("under_2p5_candidate_count"),
                0,
            ),
            "selected_allatom_near_candidate_count": _safe_int(
                selected_allatom_focus_context.get("near_candidate_count"),
                0,
            ),
            "selected_allatom_next_required_step": _text(
                selected_allatom_focus_context.get("next_required_step")
            ),
            "selected_allatom_actionability_status": _text(
                selected_allatom_actionability.get("status")
            ),
            "selected_allatom_actionability_blocked": bool(
                selected_allatom_actionability.get("blocked", False)
            ),
            "selected_allatom_actionability_brief_summary": _text(
                selected_allatom_actionability.get("brief_summary")
            ),
            "selected_allatom_actionability_human_summary": _text(
                selected_allatom_actionability.get("human_summary")
            ),
            "selected_allatom_human_summary": _joined(
                selected_allatom_actionability.get("human_summary"),
                f"Actionability: {selected_allatom_actionability.get('brief_summary')}"
                if selected_allatom_actionability.get("brief_summary")
                else "",
            ),
            "selected_allatom_actionability_block_reason": _text(
                selected_allatom_actionability.get("block_reason")
            ),
            "selected_allatom_actionability_block_reason_codes": list(
                selected_allatom_actionability.get("block_reason_codes", []) or []
            ),
            "selected_allatom_actionability_soft_guidance_reasons": list(
                selected_allatom_actionability.get("soft_guidance_reasons", []) or []
            ),
            "selected_allatom_actionability_required_calculations": list(
                selected_allatom_actionability.get("required_calculations", []) or []
            ),
            "selected_allatom_actionability_required_calculations_text": _text(
                selected_allatom_actionability.get("required_calculations_text")
            ),
            "selected_allatom_actionability_action_list": list(
                selected_allatom_actionability.get("action_list", []) or []
            ),
            "selected_allatom_actionability_action_list_text": _text(
                selected_allatom_actionability.get("action_list_text")
            ),
            "selected_allatom_actionability_claim_requirement_mode": _text(
                selected_allatom_actionability.get("claim_requirement_mode")
            ),
            "selected_allatom_actionability_claim_requirement_status": _text(
                selected_allatom_actionability.get("claim_requirement_status")
            ),
            "selected_allatom_actionability_claim_requirement_reason": _text(
                selected_allatom_actionability.get("claim_requirement_reason")
            ),
            "selected_allatom_actionability_next_expensive_lane": _text(
                selected_allatom_actionability.get("next_expensive_lane")
            ),
            "selected_allatom_actionability_next_expensive_lane_reason": _text(
                selected_allatom_actionability.get("next_expensive_lane_reason")
            ),
            "selected_allatom_actionability_translation_gate_v2_failed_metrics": list(
                selected_allatom_actionability.get("translation_gate_v2_failed_metrics", []) or []
            ),
            "selected_allatom_actionability_translation_gate_v2_missing_metrics": list(
                selected_allatom_actionability.get("translation_gate_v2_missing_metrics", []) or []
            ),
            "selected_allatom_actionability_translation_gate_v2_thresholds": dict(
                selected_allatom_actionability.get("translation_gate_v2_thresholds", {}) or {}
            ),
            "selected_allatom_raw_claim_requirement_mode": _text(
                selected_allatom_canonical.get("raw_claim_requirement_mode")
            ),
            "selected_allatom_raw_claim_required_for_final_wetlab": bool(
                selected_allatom_canonical.get("raw_claim_required_for_final_wetlab", False)
            ),
            "selected_allatom_raw_claim_required_for_commercial_readiness": bool(
                selected_allatom_canonical.get(
                    "raw_claim_required_for_commercial_readiness",
                    False,
                )
            ),
            "selected_allatom_raw_claim_requirement_reason": _text(
                selected_allatom_canonical.get("raw_claim_requirement_reason")
            ),
            "selected_allatom_effective_actionability_status": _text(
                selected_allatom_canonical.get("effective_actionability_status")
            ),
            "selected_allatom_effective_actionability_claim_requirement_mode": _text(
                selected_allatom_canonical.get(
                    "effective_actionability_claim_requirement_mode"
                )
            ),
            "selected_allatom_effective_blocking_order": _text(
                selected_allatom_canonical.get("effective_blocking_order")
            ),
            "selected_allatom_effective_primary_blocking_domain": _text(
                selected_allatom_canonical.get("effective_primary_blocking_domain")
            ),
            "selected_allatom_action_recipe_codes": list(
                selected_allatom_canonical.get("action_recipe_codes", []) or []
            ),
            "selected_allatom_action_recipe_rows": list(
                selected_allatom_canonical.get("action_recipe_rows", []) or []
            ),
            **selected_allatom_visual_fields,
            "selected_allatom_claim_gate_source": _text(
                selected_allatom_selected_summary.get("claim_gate_source")
            ),
            "selected_allatom_claim_gate_policy_version": _text(
                selected_allatom_selected_summary.get("claim_gate_policy_version")
            ),
            "selected_allatom_claim_pass_core_gate": selected_allatom_selected_summary.get(
                "pass_core_gate"
            ),
            "selected_allatom_claim_core_failed_metrics": _coerce_list(
                selected_allatom_selected_summary.get("core_failed_metrics", [])
            ),
            "selected_allatom_claim_core_missing_metrics": _coerce_list(
                selected_allatom_selected_summary.get("core_missing_metrics", [])
            ),
            "selected_allatom_claim_failed_metrics": _coerce_list(
                selected_allatom_selected_summary.get("claim_failed_metrics", [])
            ),
            "selected_allatom_claim_missing_metrics": _coerce_list(
                selected_allatom_selected_summary.get("claim_missing_metrics", [])
            ),
            "selected_allatom_claim_requirement_mode": _text(
                selected_allatom_canonical.get("raw_claim_requirement_mode")
            ),
            "selected_allatom_claim_requirement_provenance": _text(
                selected_allatom_canonical.get("raw_claim_requirement_provenance"),
                selected_allatom_selected_summary.get("claim_gate_requirement_provenance"),
                "not_reported",
            ),
            "selected_allatom_claim_required_for_final_wetlab": bool(
                selected_allatom_canonical.get("raw_claim_required_for_final_wetlab", False)
            ),
            "selected_allatom_claim_required_for_commercial_readiness": bool(
                selected_allatom_canonical.get(
                    "raw_claim_required_for_commercial_readiness",
                    False,
                )
            ),
            "selected_allatom_claim_requirement_reason": _text(
                selected_allatom_canonical.get("raw_claim_requirement_reason"),
                selected_allatom_selected_summary.get("claim_gate_requirement_reason"),
            ),
            "selected_allatom_claim_requirement_actions": list(
                dict(selected_allatom_focus_context.get("raw_claim", {}) or {}).get(
                    "requirement_actions",
                    selected_allatom_selected_summary.get("claim_gate_requirement_actions", []) or [],
                )
                or []
            ),
            "selected_allatom_commercial_replicate_count_v2": _safe_int(
                selected_allatom_selected_summary.get("commercial_replicate_count_v2"), 0
            ),
            "selected_allatom_commercial_replicate_pass_fraction_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_replicate_pass_fraction_v2"), 0.0
            ),
            "selected_allatom_commercial_median_mean_min_distance_A_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_median_mean_min_distance_A_v2"), 0.0
            ),
            "selected_allatom_commercial_mean_min_distance_iqr_A_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_mean_min_distance_iqr_A_v2"), 0.0
            ),
            "selected_allatom_commercial_median_contact_fraction_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_median_contact_fraction_v2"), 0.0
            ),
            "selected_allatom_commercial_pose_cluster_dominance_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_pose_cluster_dominance_v2"), 0.0
            ),
            "selected_allatom_commercial_pose_preservation_rmsd_A_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_pose_preservation_rmsd_A_v2"), 0.0
            ),
            "selected_allatom_commercial_backmapping_consistency_score_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_backmapping_consistency_score_v2"), 0.0
            ),
            "selected_allatom_commercial_local_minimization_survival_fraction_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_local_minimization_survival_fraction_v2"), 0.0
            ),
            "selected_allatom_commercial_binding_energy_proxy_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_binding_energy_proxy_v2"), 0.0
            ),
            "selected_allatom_commercial_stability_score_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_stability_score_v2"), 0.0
            ),
            "selected_allatom_commercial_contact_fraction_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_contact_fraction_v2"), 0.0
            ),
            "selected_allatom_commercial_binding_energy_mmpbsa_std_v2": _safe_float(
                selected_allatom_selected_summary.get("commercial_binding_energy_mmpbsa_std_v2"), 0.0
            ),
            "selected_allatom_commercial_trajectory_frames_v2": _safe_int(
                selected_allatom_selected_summary.get("commercial_trajectory_frames_v2"), 0
            ),
            "selected_allatom_commercial_hard_gate_failed_metrics_v2": list(
                selected_allatom_selected_summary.get("commercial_hard_gate_failed_metrics_v2", []) or []
            ),
            "selected_allatom_commercial_hard_gate_missing_metrics_v2": list(
                selected_allatom_selected_summary.get("commercial_hard_gate_missing_metrics_v2", []) or []
            ),
            "selected_allatom_commercial_score_thresholds_v2": dict(
                selected_allatom_selected_summary.get("commercial_score_thresholds_v2", {}) or {}
            ),
            "selected_allatom_commercial_reported_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "reported",
                    False,
                )
            ),
            "selected_allatom_commercial_schema_version": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "schema_version"
                )
            ),
            "selected_allatom_commercial_hard_gate_reported_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "hard_gate_reported",
                    False,
                )
            ),
            "selected_allatom_commercial_hard_gate_pass_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "hard_gate_pass_v1",
                    False,
                )
            ),
            "selected_allatom_commercial_overall_reported_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "overall_reported",
                    False,
                )
            ),
            "selected_allatom_commercial_overall_score_v1": _safe_float(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "overall_score_v1"
                ),
                0.0,
            ),
            "selected_allatom_commercial_risk_reported_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "risk_reported",
                    False,
                )
            ),
            "selected_allatom_commercial_risk_bucket_v1": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "risk_bucket_v1"
                )
            ),
            "selected_allatom_commercial_decision_reported_v1": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "decision_reported",
                    False,
                )
            ),
            "selected_allatom_commercial_decision_class_v1": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "decision_class_v1"
                )
            ),
            "selected_allatom_commercial_primary_upgrade_actions_v1": list(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "primary_upgrade_actions_v1",
                    [],
                )
                or []
            ),
            "selected_allatom_commercial_primary_upgrade_actions_text_v1": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "primary_upgrade_actions_text_v1"
                )
            ),
            "selected_allatom_commercial_reported_v2": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "reported_v2",
                    False,
                )
            ),
            "selected_allatom_commercial_schema_version_v2": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "schema_version_v2"
                )
            ),
            "selected_allatom_commercial_hard_gate_pass_v2": bool(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "hard_gate_pass_v2",
                    False,
                )
            ),
            "selected_allatom_commercial_soft_score_v2": _safe_float(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "soft_score_v2"
                ),
                0.0,
            ),
            "selected_allatom_commercial_confidence_score_v2": _safe_float(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "confidence_score_v2"
                ),
                0.0,
            ),
            "selected_allatom_commercial_overall_score_v2": _safe_float(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "overall_score_v2"
                ),
                0.0,
            ),
            "selected_allatom_commercial_risk_bucket_v2": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "risk_bucket_v2"
                )
            ),
            "selected_allatom_commercial_decision_class_v2": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "decision_class_v2"
                )
            ),
            "selected_allatom_commercial_primary_upgrade_actions_v2": list(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "primary_upgrade_actions_v2",
                    [],
                )
                or []
            ),
            "selected_allatom_commercial_primary_upgrade_actions_text_v2": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "primary_upgrade_actions_text_v2"
                )
            ),
            "selected_allatom_commercial_human_summary_v2": _text(
                dict(selected_allatom_focus_context.get("commercial", {}) or {}).get(
                    "human_summary_v2"
                )
            ),
            "selected_allatom_translation_gate_version": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "version"
                )
            ),
            "selected_allatom_translation_gate_focus_status": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "focus_status"
                )
            ),
            "selected_allatom_translation_gate_focus_score": _safe_float(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "focus_score"
                ),
                0.0,
            ),
            "selected_allatom_translation_gate_focus_reason": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "focus_reason"
                )
            ),
            "selected_allatom_pose_validation_reported": bool(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "reported",
                    False,
                )
            ),
            "selected_allatom_pose_validation_version": _text(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "version"
                )
            ),
            "selected_allatom_pose_validation_source": _text(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "source"
                )
            ),
            "selected_allatom_pose_validation_status": _text(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_status"
                )
            ),
            "selected_allatom_pose_validation_soft_status": _text(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_soft_status"
                )
            ),
            "selected_allatom_pose_validation_score": _safe_float(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_score"
                ),
                0.0,
            ),
            "selected_allatom_pose_validation_pass": bool(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_pass",
                    False,
                )
            ),
            "selected_allatom_pose_validation_pose_preservation_rmsd_A": dict(
                selected_allatom_focus_context.get("pose_validation", {}) or {}
            ).get("focus_pose_preservation_rmsd_A"),
            "selected_allatom_pose_validation_backmapping_consistency_score": dict(
                selected_allatom_focus_context.get("pose_validation", {}) or {}
            ).get("focus_backmapping_consistency_score"),
            "selected_allatom_pose_validation_thresholds": dict(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_thresholds",
                    {},
                )
                or {}
            ),
            "selected_allatom_pose_validation_failed_checks": list(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_failed_checks",
                    [],
                )
                or []
            ),
            "selected_allatom_pose_validation_missing_checks": list(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_missing_checks",
                    [],
                )
                or []
            ),
            "selected_allatom_pose_validation_passed_checks": list(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_passed_checks",
                    [],
                )
                or []
            ),
            "selected_allatom_pose_validation_action_codes": list(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_action_codes",
                    [],
                )
                or []
            ),
            "selected_allatom_pose_validation_blocker_codes": list(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_blocker_codes",
                    [],
                )
                or []
            ),
            "selected_allatom_pose_validation_reason": _text(
                dict(selected_allatom_focus_context.get("pose_validation", {}) or {}).get(
                    "focus_reason"
                )
            ),
            "selected_allatom_focus_shortlist_tier": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "focus_shortlist_tier"
                )
            ),
            "selected_allatom_recommended_next_expensive_lane": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "recommended_next_expensive_lane"
                )
            ),
            "selected_allatom_recommended_next_expensive_lane_reason": _text(
                dict(selected_allatom_focus_context.get("translation", {}) or {}).get(
                    "recommended_next_expensive_lane_reason"
                )
            ),
            "rescue_only_branch_templates_ready": bool(
                rh.get("rescue_only_branch_templates_ready", False)
            ),
            "rescue_only_branch_template_target_count": _safe_int(
                rh.get("rescue_only_branch_template_target_count")
            ),
            "rescue_only_branch_focus_target_id": _text(
                rh.get("rescue_only_branch_focus_target_id")
            ),
            "rescue_only_branch_focus_template_label": _text(
                rh.get("rescue_only_branch_focus_template_label")
            ),
            "rescue_only_branch_focus_surface_label": _text(
                rh.get("rescue_only_branch_focus_surface_label")
            ),
            "rescue_only_branch_focus_selected_command_kind": _text(
                rh.get("rescue_only_branch_focus_selected_command_kind")
            ),
            "rescue_only_branch_focus_selected_threshold_A": _safe_float(
                rh.get("rescue_only_branch_focus_selected_threshold_A")
            ),
            "selected_rescue_branch_next_required_step": _text(
                tcruzi_pde_rescue_only_branch_next_step,
                rh.get("selected_rescue_branch_next_required_step"),
                tpr.get("next_required_step"),
                trr.get("next_required_step"),
            ),
            "selected_manual_retry_shard_id": _text(
                _lane_shard_display(selected_manual_retry_lane),
                rh.get("selected_manual_retry_shard_id"),
            ),
            "selected_manual_retry_selected_command_kind": _text(rh.get("selected_manual_retry_selected_command_kind")),
            "selected_manual_retry_lane_label": _text(rh.get("selected_manual_retry_lane_label")),
            "selected_manual_retry_freeze_state": _text(selected_lane_summary.get("hard_freeze_state"), selected_lane_summary.get("freeze_state")),
            "selected_manual_retry_freeze_note": _text(selected_lane_summary.get("freeze_note"), selected_lane_summary.get("next_required_step")),
            "plpro_manual_retry_target_id": _text(pmr.get("target_id")),
            "plpro_manual_retry_shard_id": _text(pmr.get("shard_id")),
            "plpro_manual_retry_selected_command_kind": _text(pmr.get("selected_command_kind")),
            "mapping_fix_retry_support_ready": bool(str(mfr.get("status", "")).strip() == "wetlab_mapping_fix_retry_support_ready"),
            "mapping_fix_retry_ready_target_count": _safe_int(mfr.get("ready_target_count")),
            "mapping_fix_retry_ready_targets": _text(mfr.get("ready_targets")),
            "stage1_mapping_fix_lanes_ready": bool(str(smfl.get("status", "")).strip() == "wetlab_stage1_mapping_fix_lanes_ready"),
            "stage1_mapping_fix_ready_target_count": _safe_int(smfl.get("ready_target_count")),
            "stage1_mapping_fix_ready_targets": _text(smfl.get("ready_targets")),
            "mapping_fix_retry_policy_templates_ready": bool(str(mfrpt.get("status", "")).strip() == "wetlab_mapping_fix_retry_policy_templates_ready"),
            "mapping_fix_retry_template_target_count": _safe_int(mfrpt.get("template_target_count")),
            "mapping_fix_retry_ready_template_target_count": _safe_int(mfrpt.get("ready_target_count")),
            "mapping_fix_retry_focus_target_id": _text(mfrpt.get("focus_target_id")),
            "mapping_fix_retry_focus_template_label": _text(mfrpt.get("focus_template_label")),
            "mapping_fix_retry_focus_selected_command_kind": _text(mfrpt.get("focus_selected_command_kind")),
            "hard_target_rescue_lane_ready": bool(str(rescue_lane.get("status", "")).strip() == "wetlab_hard_target_rescue_lane_ready"),
            "hard_target_rescue_lane_target_id": _text(rescue_lane.get("target_id")),
            "hard_target_rescue_lane_shard_id": _text(rescue_lane.get("shard_id")),
            "hard_target_rescue_lane_auto_hold_streak": _safe_int(rescue_lane.get("auto_hold_streak")),
            "hard_target_rescue_lane_selected_command_kind": _text(rescue_lane.get("selected_command_kind")),
            "hard_target_rescue_lane_lane_label": _text(rescue_lane.get("lane_label")),
            "hard_target_rescue_lane_next_required_step": _text(rescue_lane.get("next_required_step")),
            "rescue_anchor_artifacts_ready": bool(str(rescue_anchors.get("status", "")).strip() == "wetlab_rescue_anchor_artifacts_ready"),
            "rescue_anchor_target_id": _text(rescue_anchors.get("target_id")),
            "rescue_anchor_artifact_count": _safe_int(rescue_anchors.get("anchor_artifact_count")),
            "rescue_anchor_rescue_only": bool(rescue_anchors.get("rescue_only", False)),
            "rescue_anchor_native_anchor_artifact": _text(rescue_anchors.get("native_anchor_artifact")),
            "rescue_anchor_pocket_anchor_artifact": _text(rescue_anchors.get("pocket_anchor_artifact")),
            "rescue_anchor_next_required_step": _text(rescue_anchors.get("next_required_step")),
            "rescue_three_bead_candidates_ready": bool(str(rescue_three_bead.get("status", "")).strip() == "wetlab_rescue_three_bead_candidates_ready"),
            "rescue_three_bead_candidate_target_id": _text(rescue_three_bead.get("target_id")),
            "rescue_three_bead_candidate_count": _safe_int(rescue_three_bead.get("candidate_count")),
            "rescue_three_bead_candidate_top_n": _safe_int(rescue_three_bead.get("top_n")),
            "rescue_three_bead_candidate_selected_command_kind": _text(rescue_three_bead.get("selected_command_kind")),
            "rescue_three_bead_candidate_selected_threshold_A": _safe_float(rescue_three_bead.get("selected_threshold_A")),
            "rescue_three_bead_candidate_next_required_step": _text(rescue_three_bead.get("next_required_step")),
            "ligand_admet_module_ready": bool(str((ligand_admet_module or {}).get("summary", {}).get("status", "")).strip() == "ligand_admet_module_ready"),
            "ligand_admet_module_status": _text((ligand_admet_module or {}).get("summary", {}).get("status")),
            "ligand_admet_target_count": _safe_int((ligand_admet_module or {}).get("summary", {}).get("target_count")),
            "ligand_admet_compound_count": _safe_int((ligand_admet_module or {}).get("summary", {}).get("compound_count")),
            "ligand_admet_green_count": _safe_int((ligand_admet_module or {}).get("summary", {}).get("green_count")),
            "ligand_admet_yellow_count": _safe_int((ligand_admet_module or {}).get("summary", {}).get("yellow_count")),
            "ligand_admet_red_count": _safe_int((ligand_admet_module or {}).get("summary", {}).get("red_count")),
            "ligand_admet_module_scope": _text((ligand_admet_module or {}).get("summary", {}).get("module_scope")),
            "ligand_admet_next_required_step": _text((ligand_admet_module or {}).get("summary", {}).get("next_required_step")),
            "partnering_stack_artifact_status": _text(raw_ps.get("status")),
            "partnering_stack_artifact_complete": _is_full_partnering_stack_summary(raw_ps),
            "campaign_terminal_state": _text(fc.get("campaign_terminal_state"), mh.get("campaign_terminal_state"), ps.get("campaign_terminal_state"), mt.get("campaign_terminal_state")),
            "ready_to_send_track_count": _safe_int(mt.get("ready_to_send_track_count"), _safe_int(fc.get("ready_to_send_track_count"), _safe_int(mh.get("ready_to_send_track_count"), _safe_int(ps.get("ready_to_send_track_count"))))),
            "next_required_step": _text(
                selected_krs1_branch_review_next_required_step,
                dpre1_priority_step,
                tcruzi_pde_rescue_only_branch_next_step,
                tcruzi_pde_rescue_review_next_step,
                _text(selected_allatom_focus_context.get("next_required_step")),
                dengue_stage6_next_required_step,
                _lbdhodh_gate51_validation_review_next_step(lbdhodh_gate51_validation_review_surface),
                stk17b_followup_review_next_step if selected_is_stk17b_followup else "",
                manual_retry_lane_next_step,
                smfl.get("next_required_step"),
                mfr.get("next_required_step"),
                rescue_lane.get("next_required_step"),
                rescue_anchors.get("next_required_step"),
                rescue_three_bead.get("next_required_step"),
                rh.get("next_required_step"),
                pqs.get("next_required_step"),
                aqs.get("next_required_step"),
                pm.get("next_required_step"),
                fs.get("next_required_step"),
                hg.get("next_required_step"),
                fc.get("next_required_step"),
                mh.get("next_required_step"),
                ps.get("next_required_step"),
                mt.get("next_required_step"),
            ),
        },
        "structured": {
            "primary_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "antitarget_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
            "primary_watch_state_artifact": "runs/wetlab_broad_screen_primary_watch_state_current.md",
            "antitarget_watch_state_artifact": "runs/wetlab_broad_screen_antitarget_watcher_state_current.md",
            "precision_monitor_artifact": "runs/wetlab_broad_screen_precision_monitor_current.md",
            "failure_surface_artifact": "runs/wetlab_primary_stage6_failure_surface_current.md",
            "primary_retry_preset_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
            "antitarget_retry_preset_artifact": "runs/wetlab_broad_screen_antitarget_throughput_bridge_current.md",
            "hold_guard_artifact": "runs/wetlab_broad_screen_primary_watch_action_current.md",
            "retry_handoff_summary_artifact": "runs/wetlab_retry_handoff_summary_current.md",
            "tcruzi_krs1_branch_review_surface_artifact": "runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
            "dengue_stage6_tuning_surface_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md",
            "dengue_exploratory_retry_lane_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md",
            "lbdhodh_gate51_validation_review_surface_artifact": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            "tcruzi_pde_rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            "tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "tcruzi_pde_rescue_operator_packet_artifact": "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md",
            "rescue_only_branch_templates_artifact": "runs/wetlab_rescue_only_branch_templates_current.md",
            "lbdhodh_stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "lbdhodh_exploratory_retry_lane_artifact": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
            "stk17b_manual_retry_lane_artifact": "runs/wetlab_stk17b_manual_retry_lane_current.md",
            "stk17b_exploratory_retry_lane_artifact": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "stk17b_exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "stk17b_followup_review_surface_artifact": "runs/wetlab_stk17b_followup_review_surface_current.md",
            "kinase_retry_policy_templates_artifact": "runs/wetlab_kinase_retry_policy_templates_current.md",
            "target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "stage6_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
            "plpro_manual_retry_lane_artifact": "runs/wetlab_plpro_manual_retry_lane_current.md",
            "mapping_fix_retry_support_artifact": "runs/wetlab_mapping_fix_retry_support_current.md",
        "stage1_mapping_fix_lanes_artifact": "runs/wetlab_stage1_mapping_fix_lanes_current.md",
        "mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
        "dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
        "hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "ligand_admet_module_artifact": "runs/ligand_admet_module_current.md",
            "tcruzi_pde_allatom_rescue_lane_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "tcruzi_pde_allatom_review_packet_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
            "cathepsin_k_allatom_refinement_lane_artifact": "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.md",
            "cathepsin_k_allatom_review_packet_artifact": "runs/wetlab_cathepsin_k_allatom_review_packet_current.md",
            "sarscov2_mpro_allatom_refinement_lane_artifact": "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.md",
            "sarscov2_mpro_allatom_review_packet_artifact": "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.md",
            "partnering_stack_artifact": "runs/wetlab_partnering_stack_current.md",
            "master_handoff_artifact": "runs/wetlab_master_handoff_dashboard_current.md",
            "final_campaign_summary_artifact": "runs/wetlab_final_campaign_summary_current.md",
            "master_terminal_review_artifact": "runs/wetlab_master_terminal_review_current.md",
        },
        "groups": groups,
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an index surface for the current wet-lab results.")
    parser.add_argument("--primary-queue-json", default=DEFAULT_PRIMARY_QUEUE_JSON)
    parser.add_argument("--antitarget-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--primary-watch-state-json", default=DEFAULT_PRIMARY_WATCH_STATE_JSON)
    parser.add_argument("--antitarget-watch-state-json", default=DEFAULT_ANTITARGET_WATCH_STATE_JSON)
    parser.add_argument("--precision-monitor-json", default=DEFAULT_PRECISION_MONITOR_JSON)
    parser.add_argument("--failure-surface-json", default=DEFAULT_FAILURE_SURFACE_JSON)
    parser.add_argument("--primary-retry-preset-json", default=DEFAULT_RETRY_PRESET_JSON)
    parser.add_argument("--antitarget-retry-preset-json", default=DEFAULT_ANTITARGET_RETRY_PRESET_JSON)
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--retry-handoff-summary-json", default=DEFAULT_RETRY_HANDOFF_JSON)
    parser.add_argument("--dpre1-branch-review-surface-json", default=DEFAULT_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-branch-review-surface-json", default=DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--dengue-stage6-tuning-surface-json", default=DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--dengue-exploratory-retry-lane-json", default=DEFAULT_DENGUE_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-rescue-review-surface-json", default=DEFAULT_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--tcruzi-pde-allatom-rescue-lane-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_RESCUE_LANE_JSON)
    parser.add_argument("--tcruzi-pde-allatom-review-packet-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--cathepsin-k-allatom-refinement-lane-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_REFINEMENT_LANE_JSON)
    parser.add_argument("--cathepsin-k-allatom-review-packet-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-refinement-lane-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_REFINEMENT_LANE_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-review-packet-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--lbdhodh-stage6-tuning-surface-json", default=DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--lbdhodh-exploratory-retry-lane-json", default=DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-manual-retry-lane-json", default=DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-retry-lane-json", default=DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-followup-lane-json", default=DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
    parser.add_argument("--stk17b-followup-review-surface-json", default=DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--kinase-retry-policy-templates-json", default=DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--target-retry-policy-templates-json", default=DEFAULT_TARGET_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--plpro-manual-retry-lane-json", default=DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--mapping-fix-retry-support-json", default=DEFAULT_MAPPING_FIX_RETRY_SUPPORT_JSON)
    parser.add_argument("--stage1-mapping-fix-lanes-json", default=DEFAULT_STAGE1_MAPPING_FIX_LANES_JSON)
    parser.add_argument("--mapping-fix-retry-policy-templates-json", default=DEFAULT_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--hard-target-rescue-lane-json", default=DEFAULT_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--rescue-anchor-artifacts-json", default=DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--rescue-three-bead-candidates-json", default=DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--partnering-stack-json", default=DEFAULT_PARTNERING_STACK_JSON)
    parser.add_argument("--master-handoff-dashboard-json", default=DEFAULT_MASTER_HANDOFF_JSON)
    parser.add_argument("--final-campaign-summary-json", default=DEFAULT_FINAL_SUMMARY_JSON)
    parser.add_argument("--master-terminal-review-json", default=DEFAULT_MASTER_TERMINAL_REVIEW_JSON)
    parser.add_argument("--selected-allatom-visual-bundle-json", default=DEFAULT_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON)
    parser.add_argument("--ligand-admet-module-json", default=DEFAULT_LIGAND_ADMET_MODULE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.primary_queue_json),
        maybe_load_json(args.antitarget_queue_json),
        maybe_load_json(args.primary_watch_state_json),
        maybe_load_json(args.antitarget_watch_state_json),
        maybe_load_json(args.precision_monitor_json),
        maybe_load_json(args.failure_surface_json),
        maybe_load_json(args.primary_retry_preset_json),
        maybe_load_json(args.antitarget_retry_preset_json),
        maybe_load_json(args.hold_guard_json),
        maybe_load_json(args.retry_handoff_summary_json),
        maybe_load_json(args.dpre1_branch_review_surface_json),
        maybe_load_json(args.dengue_stage6_tuning_surface_json),
        maybe_load_json(args.dengue_exploratory_retry_lane_json),
        maybe_load_json(args.lbdhodh_gate51_validation_review_surface_json),
        maybe_load_json(args.tcruzi_pde_rescue_review_surface_json),
        maybe_load_json(args.tcruzi_pde_promoted_top4_review_packet_json),
        maybe_load_json(args.tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.lbdhodh_stage6_tuning_surface_json),
        maybe_load_json(args.lbdhodh_exploratory_retry_lane_json),
        maybe_load_json(args.stk17b_manual_retry_lane_json),
        maybe_load_json(args.stk17b_exploratory_retry_lane_json),
        maybe_load_json(args.stk17b_exploratory_followup_lane_json),
        maybe_load_json(args.stk17b_followup_review_surface_json),
        maybe_load_json(args.kinase_retry_policy_templates_json),
        maybe_load_json(args.target_retry_policy_templates_json),
        maybe_load_json(args.plpro_manual_retry_lane_json),
        maybe_load_json(args.mapping_fix_retry_support_json),
        maybe_load_json(args.stage1_mapping_fix_lanes_json),
        maybe_load_json(args.mapping_fix_retry_policy_templates_json),
        maybe_load_json(args.hard_target_rescue_lane_json),
        maybe_load_json(args.rescue_anchor_artifacts_json),
        maybe_load_json(args.rescue_three_bead_candidates_json),
        maybe_load_json(args.partnering_stack_json),
        maybe_load_json(args.master_handoff_dashboard_json),
        maybe_load_json(args.final_campaign_summary_json),
        maybe_load_json(args.master_terminal_review_json),
        maybe_load_json(args.tcruzi_krs1_branch_review_surface_json),
        maybe_load_json(args.tcruzi_pde_allatom_rescue_lane_json),
        maybe_load_json(args.tcruzi_pde_allatom_review_packet_json),
        maybe_load_json(args.cathepsin_k_allatom_refinement_lane_json),
        maybe_load_json(args.cathepsin_k_allatom_review_packet_json),
        maybe_load_json(args.sarscov2_mpro_allatom_refinement_lane_json),
        maybe_load_json(args.sarscov2_mpro_allatom_review_packet_json),
        maybe_load_json(args.selected_allatom_visual_bundle_json),
        maybe_load_json(args.ligand_admet_module_json),
    )
    write_index_artifact(args.out_md, payload)


if __name__ == "__main__":
    main()
