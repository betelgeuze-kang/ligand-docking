#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, resolve
from tools.wetlab.wetlab_selected_allatom_canonical import resolve_selected_allatom_canonical
from tools.wetlab.wetlab_selected_allatom_visual import (
    resolve_selected_allatom_visual_bundle,
    selected_allatom_visual_surface_fields,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRECISION_MONITOR_JSON = "runs/wetlab_broad_screen_precision_monitor_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_ANTITARGET_PROGRESS_JSON = "runs/wetlab_broad_screen_antitarget_progress_current.json"
DEFAULT_FAILURE_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
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
DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON = "runs/wetlab_plpro_manual_retry_lane_current.json"
DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_kinase_retry_policy_templates_current.json"
DEFAULT_TARGET_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_mapping_fix_retry_policy_templates_current.json"
DEFAULT_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON = "runs/selected_allatom_visual_bundle_current.json"
DEFAULT_OUT_MD = "runs/wetlab_monitor_semantics_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _artifact_json_path(path_like: str) -> str:
    text = str(path_like or "").strip()
    if not text:
        return ""
    path = Path(text)
    if path.suffix.lower() == ".md":
        path = path.with_suffix(".json")
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


def _selected_allatom_focus_artifact_json_path(payload: dict[str, Any]) -> str:
    explicit_artifact = _text(
        payload.get("selected_allatom_focus_artifact"),
        payload.get("selected_allatom_readiness_source_artifact"),
    )
    if explicit_artifact:
        return _artifact_json_path(explicit_artifact)
    surface_label = _text(
        payload.get("selected_allatom_surface_label"),
        payload.get("allatom_family_focus_surface_label"),
    )
    if not surface_label:
        return ""
    base_name = surface_label if surface_label.startswith("wetlab_") else f"wetlab_{surface_label}"
    return str(ROOT / "runs" / f"{base_name}_current.json")


def _load_artifact_summary(path_like: str) -> dict[str, Any]:
    artifact_json_path = _artifact_json_path(path_like)
    if not artifact_json_path:
        return {}
    return _summary(maybe_load_json(artifact_json_path))


def _selected_allatom_actionability_fallback(
    *,
    final_gate_pass: bool,
    operator_review_ready: bool,
    commercial_hard_gate_blocked: bool,
    claim_gate_available: bool,
    claim_ready_for_allatom: bool,
    translation_status: str,
    translation_reason: str,
    shortlist_tier: str,
    next_expensive_lane: str,
    next_expensive_lane_reason: str,
    next_required_step: str,
) -> dict[str, Any]:
    inferred_next_expensive_lane = _text(
        next_expensive_lane,
        "defer_expensive_lane"
        if shortlist_tier == "defer"
        or (translation_status and next_expensive_lane_reason)
        or "defer_expensive_lane" in str(next_required_step or "").lower()
        or "defer expensive lane" in str(next_required_step or "").lower()
        or "enter_expensive_lane" in str(next_required_step or "").lower()
        or "enter expensive lane" in str(next_required_step or "").lower()
        else "",
    )
    hard_block_present = bool(
        commercial_hard_gate_blocked
        or _text(translation_status).lower() in {"fail", "blocked"}
    )
    claim_requirement_mode = "semi_hard" if claim_gate_available and not hard_block_present else "not_applicable"
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
    status = "ready"
    if not final_gate_pass:
        if hard_block_present:
            status = "hard_blocked"
        elif claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom:
            status = "semi_hard_blocked"
        elif inferred_next_expensive_lane or shortlist_tier:
            status = "soft_guided"
        else:
            status = "blocked"
    required_calculations: list[str] = []
    action_list: list[dict[str, Any]] = []
    if claim_requirement_mode == "semi_hard":
        action_list.append(
            {
                "severity": "semi_hard",
                "category": "claim_equivalence",
                "action": "resolve_claim_equivalence_gate",
                "status": "satisfied" if claim_ready_for_allatom else "required",
                "claim_requirement_mode": "semi_hard",
                "reason": claim_requirement_reason,
            }
        )
        if not claim_ready_for_allatom:
            required_calculations.append("resolve_claim_equivalence_gate")
    if inferred_next_expensive_lane:
        action_list.append(
            {
                "severity": "soft",
                "category": "next_expensive_lane",
                "action": "defer_expensive_lane" if inferred_next_expensive_lane == "defer_expensive_lane" else "enter_expensive_lane",
                "status": "deferred" if inferred_next_expensive_lane == "defer_expensive_lane" else "queued",
                "lane": inferred_next_expensive_lane,
                "reason": next_expensive_lane_reason,
            }
        )
    human_summary = _joined(
        f"{status.replace('_', ' ')}: {claim_requirement_reason}" if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else status.replace("_", " "),
        f"required calculations: {', '.join(required_calculations)}" if required_calculations else "",
        f"soft guidance: {translation_reason}" if translation_reason else "",
        f"next expensive lane: {inferred_next_expensive_lane}" if inferred_next_expensive_lane else "",
    )
    brief_summary = _joined(
        f"{status.replace('_', ' ')}" if status else "",
        f"claim {claim_requirement_mode}:{claim_requirement_status}" if claim_requirement_mode == "semi_hard" else "",
        f"lane {inferred_next_expensive_lane}" if inferred_next_expensive_lane else "",
    )
    action_list_text = " | ".join(
        f"{item['severity']}:{item['action']}[{item['status']}]" + (f" lane={item['lane']}" if item.get("lane") else "")
        for item in action_list
    )
    return {
        "status": status,
        "blocked": bool(status != "ready"),
        "block_reason": claim_requirement_reason if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else (
            "commercial hard gate failed" if commercial_hard_gate_blocked else ""
        ),
        "block_reason_codes": ["claim_equivalence_gate_semi_hard"] if claim_requirement_mode == "semi_hard" and not claim_ready_for_allatom else (["commercial_hard_gate_failed"] if commercial_hard_gate_blocked else []),
        "soft_guidance_reasons": [f"translation_gate_focus:{translation_status}"] if translation_status else [],
        "required_calculations": required_calculations,
        "required_calculations_text": ", ".join(required_calculations),
        "action_list": action_list,
        "action_list_text": action_list_text,
        "claim_requirement_mode": claim_requirement_mode,
        "claim_requirement_status": claim_requirement_status,
        "claim_requirement_reason": claim_requirement_reason,
        "next_expensive_lane": inferred_next_expensive_lane,
        "next_expensive_lane_reason": next_expensive_lane_reason,
        "translation_gate_v2_failed_metrics": [],
        "translation_gate_v2_missing_metrics": [],
        "translation_gate_v2_thresholds": {},
        "human_summary": human_summary,
        "brief_summary": brief_summary,
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed"}:
        return False
    return None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item or "").strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _resolve_bool_value(
    payload: dict[str, Any],
    *keys: str,
    default: bool = False,
    default_source: str = "default",
) -> tuple[bool, str]:
    for key in keys:
        value = _safe_bool(payload.get(key))
        if value is not None:
            return value, key
    return default, default_source


def _gate_state(
    payload: dict[str, Any],
    *,
    operator_ready_keys: tuple[str, ...],
    wetlab_gate_keys: tuple[str, ...],
    final_gate_keys: tuple[str, ...],
    claim_available_keys: tuple[str, ...] = (),
    claim_ready_keys: tuple[str, ...] = (),
    legacy_ready: bool = False,
    legacy_wetlab_ready: bool | None = None,
    legacy_final_ready: bool | None = None,
) -> dict[str, Any]:
    if legacy_wetlab_ready is None:
        legacy_wetlab_ready = legacy_ready
    if legacy_final_ready is None:
        legacy_final_ready = legacy_wetlab_ready
    operator_ready, operator_ready_source = _resolve_bool_value(
        payload,
        *operator_ready_keys,
        default=legacy_ready,
        default_source="legacy_default",
    )
    wetlab_gate_pass, wetlab_gate_source = _resolve_bool_value(
        payload,
        *wetlab_gate_keys,
        default=legacy_wetlab_ready,
        default_source="legacy_default",
    )
    wetlab_final_gate_pass, wetlab_final_gate_source = _resolve_bool_value(
        payload,
        *final_gate_keys,
        default=legacy_final_ready,
        default_source=wetlab_gate_source,
    )
    claim_gate_available, claim_gate_source = _resolve_bool_value(
        payload,
        *claim_available_keys,
        default=False,
    )
    claim_ready_for_allatom, claim_ready_source = _resolve_bool_value(
        payload,
        *claim_ready_keys,
        default=False,
    )
    return {
        "packet_ready_for_operator_review": operator_ready,
        "packet_ready_for_operator_review_source": operator_ready_source,
        "wetlab_gate_pass": wetlab_gate_pass,
        "wetlab_gate_source": wetlab_gate_source,
        "wetlab_final_gate_pass": wetlab_final_gate_pass,
        "wetlab_final_gate_source": wetlab_final_gate_source,
        "claim_gate_available": claim_gate_available,
        "claim_gate_source": claim_gate_source,
        "claim_ready_for_allatom": claim_ready_for_allatom,
        "claim_ready_source": claim_ready_source,
    }


def _compound_display_name(*values: Any) -> str:
    return _text(*values)


def _percent(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100.0, 1)


def _rate_per_hour(minutes: float) -> float:
    if minutes <= 0:
        return 0.0
    return round(60.0 / minutes, 2)


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _minutes_between(start: datetime | None, end: datetime | None) -> float:
    if start is None or end is None:
        return 0.0
    return max((end - start).total_seconds() / 60.0, 0.0)


def _status_kind(status: Any) -> str:
    text = str(status or "").strip()
    if "result_ready" in text:
        return "success"
    if "explicit_hold" in text:
        return "hold"
    if "running" in text:
        return "running"
    return ""


def _target_row_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")).strip(): dict(row)
        for row in rows
        if str(row.get("target_id", "")).strip()
    }


def _stage6_retry_template_summary(target_retry_policy_templates: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(target_retry_policy_templates)
    rows = [dict(row) for row in ((target_retry_policy_templates or {}).get("rows", []) or [])]
    stage6_rows = [
        row
        for row in rows
        if _text(row.get("row_kind")) == "target_retry_policy_template"
        and _text(row.get("template_scope")) == "guarded_stage6_tuning_candidate"
    ]
    if not summary or not stage6_rows:
        return {}
    gate45_rows = [row for row in stage6_rows if "gate45" in _text(row.get("selected_command_kind"))]
    gate51_rows = [row for row in stage6_rows if "gate51" in _text(row.get("selected_command_kind"))]
    focus_row = next(
        (row for row in stage6_rows if _text(row.get("target_id")) == "Dengue NS2B-NS3 protease"),
        next((row for row in stage6_rows if _text(row.get("target_id")) == "Cathepsin K"), stage6_rows[0]),
    )
    return {
        "status": summary.get("status", ""),
        "ready_targets": "; ".join(_text(row.get("target_id")) for row in stage6_rows if _text(row.get("target_id"))),
        "gate45_targets": "; ".join(_text(row.get("target_id")) for row in gate45_rows if _text(row.get("target_id"))),
        "gate51_targets": "; ".join(_text(row.get("target_id")) for row in gate51_rows if _text(row.get("target_id"))),
        "template_target_count": len(stage6_rows),
        "gate45_candidate_target_count": len(gate45_rows),
        "gate51_candidate_target_count": len(gate51_rows),
        "focus_target_id": _text(focus_row.get("target_id")),
        "focus_template_label": _text(focus_row.get("template_label")),
        "focus_selected_command_kind": _text(focus_row.get("selected_command_kind")),
        "focus_selected_threshold_A": _safe_float(focus_row.get("selected_threshold_A"), 0.0),
        "next_required_step": _text(focus_row.get("next_required_step")),
        "policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
    }


def _dengue_stage6_summary(
    execution_queue: dict[str, Any] | None,
    dengue_stage6_tuning_surface: dict[str, Any] | None,
    dengue_exploratory_retry_lane: dict[str, Any] | None,
) -> dict[str, Any]:
    queue = _summary(execution_queue)
    tuning = _summary(dengue_stage6_tuning_surface)
    lane = _summary(dengue_exploratory_retry_lane)
    tuning_ready = _text(tuning.get("status")) == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"
    lane_ready = _text(lane.get("status")) == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"
    if not tuning_ready and not lane_ready:
        return {}
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
    shard_id = _text(
        queue_shard_id if queue_priority else "",
        lane.get("shard_id"),
        tuning.get("next_retry_shard_id"),
    )
    threshold = _safe_float(tuning.get("recommended_observed_threshold_A"), 0.0)
    command_kind = _text(lane.get("selected_command_kind"), tuning.get("immediately_runnable_command_kind"))
    lane_label = _text(lane.get("lane_label"))
    next_required_step = _text(
        queue_next_required_step if queue_priority else "",
        lane.get("next_required_step"),
        tuning.get("next_required_step"),
    )
    source_priority = "execution_queue" if queue_priority else "exploratory_lane" if lane_ready else "tuning_surface"
    return {
        "status": _text(
            queue_status if queue_priority else "",
            lane.get("status"),
            tuning.get("status"),
            default="missing",
        ),
        "source_priority": source_priority,
        "target_id": target_id,
        "tuning_ready": tuning_ready,
        "recommended_threshold_A": threshold,
        "immediately_runnable_command_kind": _text(tuning.get("immediately_runnable_command_kind")),
        "retry_lane_ready": lane_ready,
        "ready_for_manual_retry": bool(lane.get("ready_for_manual_retry", False)),
        "shard_id": shard_id,
        "selected_command_kind": command_kind,
        "lane_label": lane_label,
        "next_required_step": _text(
            next_required_step,
            (
                "Promote Dengue NS2B-NS3 protease stage6 tuned retry, keep the default lane closed, and reserve any future Dengue reopen for an explicit new review."
                if tuning_ready
                else ""
            ),
        ),
        "focus_target_id": target_id,
        "focus_template_label": lane_label or "dengue_stage6_tuned_retry",
        "focus_selected_command_kind": command_kind,
        "focus_selected_threshold_A": threshold,
    }


def _dpre1_branch_review_summary(dpre1_branch_review_surface: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(dpre1_branch_review_surface)
    if not summary or _text(summary.get("status")) != "wetlab_dpre1_branch_review_surface_ready":
        return {}
    return {
        "status": _text(summary.get("status"), default="missing"),
        "target_id": _text(summary.get("target_id"), "DprE1"),
        "branch_label": _text(summary.get("branch_label"), "dpre1_branch_review"),
        "branch_state": _text(summary.get("branch_state"), "dpre1_result_review_resolved"),
        "source_priority": _text(summary.get("source_priority"), "result_review"),
        "decision_source_priority": _text(summary.get("decision_source_priority"), "result_summary"),
        "serialized_queue_rank": _safe_int(summary.get("serialized_queue_rank", 3), 3),
        "serialized_run_order": _text(summary.get("serialized_run_order"), "3_of_5_in_wave2"),
        "partner_track_id": _text(summary.get("partner_track_id"), "TB_Alliance"),
        "result_review_status": _text(summary.get("result_review_status"), "dpre1_result_review_ready"),
        "result_summary_status": _text(summary.get("result_summary_status"), "completed"),
        "launch_packet_status": _text(summary.get("launch_packet_status"), "dpre1_launch_packet_ready"),
        "run_record_status": _text(summary.get("run_record_status"), "dpre1_run_record_ready"),
        "successor_target": _text(summary.get("successor_target"), "T. cruzi KRS1"),
        "successor_gate_state": _text(summary.get("successor_gate_state"), "open_for_tcruzi_krs1_execution"),
        "successor_gate_open": bool(summary.get("successor_gate_open", True)),
        "stage6_tuning_surface_ready": bool(summary.get("stage6_tuning_surface_ready", False)),
        "stage6_tuning_source_priority": _text(summary.get("stage6_tuning_source_priority"), "stage6_tuning_surface"),
        "stage6_tuning_recommended_threshold_A": _safe_float(summary.get("stage6_tuning_recommended_threshold_A"), 0.0),
        "stage6_tuning_immediately_runnable_command_kind": _text(summary.get("stage6_tuning_immediately_runnable_command_kind")),
        "stage6_tuning_next_required_step": _text(summary.get("stage6_tuning_next_required_step")),
        "exploratory_retry_lane_ready": bool(summary.get("exploratory_retry_lane_ready", False)),
        "exploratory_source_priority": _text(summary.get("exploratory_source_priority"), "exploratory_lane"),
        "exploratory_retry_lane_label": _text(summary.get("exploratory_retry_lane_label"), "exploratory_gate5.1_candidate"),
        "exploratory_retry_selected_command_kind": _text(summary.get("exploratory_retry_selected_command_kind")),
        "exploratory_retry_selected_threshold_A": _safe_float(summary.get("exploratory_retry_selected_threshold_A"), 0.0),
        "exploratory_retry_next_required_step": _text(summary.get("exploratory_retry_next_required_step")),
        "next_required_step": _text(summary.get("next_required_step")),
        "branch_review_ready": bool(summary.get("branch_review_ready", False)),
    }


def _krs1_branch_review_summary(krs1_branch_review_surface: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(krs1_branch_review_surface)
    if not summary or _text(summary.get("status")) != "wetlab_tcruzi_krs1_branch_review_surface_ready":
        return {}
    return {
        "status": _text(summary.get("status"), default="missing"),
        "target_id": _text(summary.get("target_id"), "T. cruzi KRS1"),
        "branch_label": _text(summary.get("branch_label"), "tcruzi_krs1_guarded_gate51_branch"),
        "branch_state": _text(summary.get("branch_state"), "guarded_gate51_review_default_lane_closed"),
        "source_priority": _text(summary.get("source_priority"), "guarded_branch_summary"),
        "decision_source_priority": _text(summary.get("decision_source_priority"), "guarded_operator_packet"),
        "serialized_queue_rank": _safe_int(summary.get("serialized_queue_rank", 4), 4),
        "serialized_run_order": _text(summary.get("serialized_run_order"), "guarded_review_hold"),
        "partner_track_id": _text(summary.get("partner_track_id"), "DNDi_Chagas_backup"),
        "result_review_status": _text(summary.get("result_review_status"), "tcruzi_krs1_result_review_ready"),
        "result_summary_status": _text(summary.get("result_summary_status"), "completed"),
        "launch_packet_status": _text(summary.get("launch_packet_status"), "tcruzi_krs1_launch_packet_ready"),
        "run_record_status": _text(summary.get("run_record_status"), "tcruzi_krs1_run_record_ready"),
        "successor_target": _text(summary.get("successor_target"), "LRRK2"),
        "successor_gate_state": _text(summary.get("successor_gate_state"), "blocked_pending_tcruzi_krs1_guarded_review"),
        "successor_gate_open": bool(summary.get("successor_gate_open", False)),
        "stage6_tuning_surface_ready": bool(summary.get("stage6_tuning_surface_ready", False)),
        "stage6_tuning_source_priority": _text(summary.get("stage6_tuning_source_priority"), "stage6_tuning_surface"),
        "stage6_tuning_recommended_threshold_A": _safe_float(summary.get("stage6_tuning_recommended_threshold_A"), 0.0),
        "stage6_tuning_immediately_runnable_command_kind": _text(summary.get("stage6_tuning_immediately_runnable_command_kind")),
        "stage6_tuning_next_required_step": _text(summary.get("stage6_tuning_next_required_step")),
        "exploratory_retry_lane_ready": bool(summary.get("exploratory_retry_lane_ready", False)),
        "exploratory_source_priority": _text(summary.get("exploratory_source_priority"), "exploratory_lane"),
        "exploratory_retry_lane_label": _text(summary.get("exploratory_retry_lane_label"), "exploratory_gate5.1_candidate"),
        "exploratory_retry_selected_command_kind": _text(summary.get("exploratory_retry_selected_command_kind")),
        "exploratory_retry_selected_threshold_A": _safe_float(summary.get("exploratory_retry_selected_threshold_A"), 0.0),
        "exploratory_retry_next_required_step": _text(summary.get("exploratory_retry_next_required_step")),
        "next_required_step": _text(summary.get("next_required_step")),
        "branch_review_ready": bool(summary.get("branch_review_ready", False)),
    }


def _queue_rows(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [dict(row) for row in ((payload or {}).get("rows", []) or [])]


def _current_rates_from_monitor(monitor_summary: dict[str, Any], monitor_rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows_by_target = _target_row_map(monitor_rows)
    focus_target_id = str(monitor_summary.get("focus_target_id", "")).strip()
    focus_row = rows_by_target.get(focus_target_id, {}) if focus_target_id else {}

    success_rows = [dict(row) for row in monitor_rows if _safe_int(row.get("completed_shards", 0), 0) > 0]
    hold_rows = [dict(row) for row in monitor_rows if _safe_int(row.get("held_shards", 0), 0) > 0]

    success_medians = [
        _safe_float(row.get("median_completed_shard_minutes", 0.0), 0.0)
        for row in success_rows
        if _safe_float(row.get("median_completed_shard_minutes", 0.0), 0.0) > 0
    ]
    hold_medians = [
        _safe_float(row.get("hold_median_completed_shard_minutes", 0.0), 0.0)
        for row in hold_rows
        if _safe_float(row.get("hold_median_completed_shard_minutes", 0.0), 0.0) > 0
    ]
    recent_success_medians = [
        _safe_float(row.get("recent_median_completed_shard_minutes", 0.0), 0.0)
        for row in success_rows
        if _safe_float(row.get("recent_median_completed_shard_minutes", 0.0), 0.0) > 0
    ]

    primary_success_rate = _rate_per_hour(_safe_float(monitor_summary.get("median_completed_shard_minutes", 0.0), 0.0))
    primary_recent_success_rate = _rate_per_hour(_safe_float(monitor_summary.get("recent_median_completed_shard_minutes", 0.0), 0.0))
    primary_hold_rate = _rate_per_hour(median(hold_medians)) if hold_medians else 0.0
    counter_success_rate = primary_success_rate
    counter_hold_rate = primary_hold_rate

    focus_kind = _status_kind(focus_row.get("queue_status", ""))
    focus_hint = "successful_resolved" if focus_kind == "success" else "held_resolved" if focus_kind == "hold" else "running_or_dispatch"

    return {
        "focus_target_id": focus_target_id,
        "focus_shard_id": str(monitor_summary.get("focus_shard_id", "")).strip(),
        "focus_kind": focus_kind,
        "focus_hint": focus_hint,
        "primary_success_rate_shards_per_hour": primary_success_rate,
        "primary_recent_success_rate_shards_per_hour": primary_recent_success_rate,
        "primary_hold_rate_shards_per_hour": primary_hold_rate,
        "counter_success_rate_shards_per_hour": counter_success_rate,
        "counter_hold_rate_shards_per_hour": counter_hold_rate,
        "primary_success_runtime_median_minutes": _safe_float(monitor_summary.get("median_completed_shard_minutes", 0.0), 0.0),
        "primary_success_runtime_recent_median_minutes": _safe_float(monitor_summary.get("recent_median_completed_shard_minutes", 0.0), 0.0),
        "primary_hold_runtime_median_minutes": round(median(hold_medians), 1) if hold_medians else 0.0,
        "primary_success_runtime_samples": len(success_medians),
        "primary_hold_runtime_samples": len(hold_medians),
        "counter_success_runtime_samples": len(success_medians),
        "counter_hold_runtime_samples": len(hold_medians),
        "focus_current_elapsed_minutes": _safe_float(monitor_summary.get("focus_elapsed_minutes", 0.0), 0.0),
        "focus_signal_age_minutes": _safe_float(monitor_summary.get("focus_signal_age_minutes", 0.0), 0.0),
        "focus_heartbeat_count": _safe_int(monitor_summary.get("focus_heartbeat_count", 0), 0),
        "focus_event_count": _safe_int(monitor_summary.get("focus_event_count", 0), 0),
        "focus_estimated_running_shard_pct": _safe_float(monitor_summary.get("focus_estimated_running_shard_pct", 0.0), 0.0),
    }


def _current_rates_from_antitarget_progress(progress_payload: dict[str, Any] | None) -> dict[str, Any]:
    rows = [dict(row) for row in ((progress_payload or {}).get("rows", []) or [])]
    success_minutes = [
        _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at")))
        for row in rows
        if _status_kind(row.get("queue_status", "")) == "success"
    ]
    hold_minutes = [
        _minutes_between(_parse_ts(row.get("started_at")), _parse_ts(row.get("completed_at") or row.get("updated_at")))
        for row in rows
        if _status_kind(row.get("queue_status", "")) == "hold"
    ]
    success_minutes = [value for value in success_minutes if value > 0]
    hold_minutes = [value for value in hold_minutes if value > 0]
    success_median = round(median(success_minutes), 1) if success_minutes else 0.0
    hold_median = round(median(hold_minutes), 1) if hold_minutes else 0.0
    recent_success_median = round(median(success_minutes[-3:]), 1) if success_minutes else 0.0
    return {
        "success_rate_shards_per_hour": _rate_per_hour(success_median),
        "hold_rate_shards_per_hour": _rate_per_hour(hold_median),
        "success_runtime_median_minutes": success_median,
        "hold_runtime_median_minutes": hold_median,
        "recent_success_runtime_median_minutes": recent_success_median,
        "success_runtime_samples": len(success_minutes),
        "hold_runtime_samples": len(hold_minutes),
    }


def _format_rate_label(rate: float) -> str:
    return f"{rate:.2f}/h" if rate > 0 else "0.00/h"


def _hard_target_rescue_lane_summary(hard_target_rescue_lane: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(hard_target_rescue_lane)
    if not summary:
        return {}
    target_id = _text(summary.get("target_id"), summary.get("focus_target_id"))
    shard_id = _text(summary.get("shard_id"), summary.get("focus_shard_id"))
    stage1_ok = bool(summary.get("stage1_ok", summary.get("stage1_passed", False)))
    stage6_fail = bool(summary.get("stage6_fail", summary.get("stage6_failed", False)))
    auto_hold_streak = _safe_int(summary.get("auto_hold_streak", summary.get("hold_streak", 0)), 0)
    rescue_eligible = bool(summary.get("rescue_eligible", stage1_ok and stage6_fail and auto_hold_streak > 0))
    next_required_step = _text(summary.get("next_required_step"))
    if not next_required_step and target_id:
        next_required_step = (
            f"Run the hard-target rescue lane for {target_id}"
            + (f" {shard_id}" if shard_id else "")
            + "; keep the default lane closed."
        )
    return {
        "status": _text(summary.get("status"), default="missing"),
        "target_id": target_id,
        "shard_id": shard_id,
        "stage1_ok": stage1_ok,
        "stage6_fail": stage6_fail,
        "auto_hold_streak": auto_hold_streak,
        "rescue_eligible": rescue_eligible,
        "selected_command_kind": _text(summary.get("selected_command_kind"), summary.get("preferred_command_kind"), summary.get("command_kind")),
        "lane_label": _text(summary.get("lane_label"), summary.get("rescue_lane_label"), "hard_target_rescue_lane"),
        "next_required_step": next_required_step,
        "rescue_anchor_artifact_count": _safe_int(summary.get("rescue_anchor_artifact_count", summary.get("anchor_artifact_count", 0)), 0),
        "three_bead_candidate_count": _safe_int(summary.get("three_bead_candidate_count", summary.get("candidate_count", 0)), 0),
    }


def _rescue_anchor_artifacts_summary(rescue_anchor_artifacts: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(rescue_anchor_artifacts)
    if not summary:
        return {}
    target_id = _text(summary.get("target_id"), summary.get("focus_target_id"))
    anchor_artifact_count = _safe_int(summary.get("anchor_artifact_count", summary.get("rescue_anchor_artifact_count", 0)), 0)
    rescue_only = bool(summary.get("rescue_only", anchor_artifact_count > 0))
    next_required_step = _text(summary.get("next_required_step"))
    if not next_required_step and target_id:
        next_required_step = f"Review rescue anchors for {target_id}; keep the default lane closed."
    return {
        "status": _text(summary.get("status"), default="missing"),
        "target_id": target_id,
        "rescue_only": rescue_only,
        "anchor_artifact_count": anchor_artifact_count,
        "native_anchor_artifact": _text(summary.get("native_anchor_artifact")),
        "pocket_anchor_artifact": _text(summary.get("pocket_anchor_artifact")),
        "next_required_step": next_required_step,
    }


def _rescue_three_bead_candidates_summary(rescue_three_bead_candidates: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary(rescue_three_bead_candidates)
    if not summary:
        return {}
    target_id = _text(summary.get("target_id"), summary.get("focus_target_id"))
    candidate_count = _safe_int(summary.get("candidate_count", summary.get("three_bead_candidate_count", 0)), 0)
    top_n = _safe_int(summary.get("top_n", summary.get("candidate_top_n", 0)), 0)
    if not top_n and candidate_count:
        top_n = min(candidate_count, 3)
    next_required_step = _text(summary.get("next_required_step"))
    if not next_required_step and target_id:
        next_required_step = f"Review 3-bead rescue candidates for {target_id}; keep the default lane closed."
    return {
        "status": _text(summary.get("status"), default="missing"),
        "target_id": target_id,
        "candidate_count": candidate_count,
        "top_n": top_n,
        "selected_command_kind": _text(summary.get("selected_command_kind"), summary.get("preferred_command_kind")),
        "selected_threshold_A": _safe_float(summary.get("selected_threshold_A", summary.get("threshold_A", 0.0)), 0.0),
        "next_required_step": next_required_step,
    }


def _manual_retry_next_step_from_lane(lane_payload: dict[str, Any] | None) -> str:
    lane = _summary(lane_payload)
    lane_label = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    status = _text(lane.get("status"))
    selectable = bool(lane.get("ready_for_manual_retry", False)) or (
        "followup" in lane_label and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
    ) or (
        status.startswith("wetlab_lbdhodh_exploratory_retry_lane_")
        and _text(lane.get("queue_status")) == "running"
        and bool(_text(lane.get("next_required_step")))
    )
    if selectable:
        explicit_next_step = _text(lane.get("next_required_step"))
        if explicit_next_step:
            return explicit_next_step
        target_id = _text(lane.get("target_id"))
        shard_id = _text(lane.get("shard_id"))
        selected_kind = _text(lane.get("selected_command_kind"))
        followup_shards = _text(lane.get("followup_shard_ids"))
        if "followup" in lane_label:
            label = "exploratory gate4.5 follow-up runner"
            freeze_clause = (
                f"keep auto-start hard-frozen and review follow-up shards {followup_shards} before reopening."
                if followup_shards
                else "keep auto-start hard-frozen."
            )
        elif "gate55" in selected_kind:
            label = "tuned gate55 manual retry runner"
            freeze_clause = "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        elif "gate45" in selected_kind:
            label = "exploratory gate4.5 manual retry runner"
            freeze_clause = "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        else:
            label = "manual retry runner"
            freeze_clause = "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        if target_id and shard_id:
            return f"Run the {target_id} {label} for {shard_id}; {freeze_clause}"
        if target_id:
            return f"Run the {target_id} {label}; {freeze_clause}"
    return ""


def _lane_shard_display(lane_payload: dict[str, Any] | None) -> str:
    lane = _summary(lane_payload)
    lane_label = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    if lane_label == "exploratory_gate4.5_followup":
        return _text(lane.get("shard_id"), lane.get("followup_shard_ids"))
    return _text(lane.get("shard_id"))


def _select_manual_retry_lane(
    retry_handoff_summary: dict[str, Any] | None,
    *lane_payloads: dict[str, Any] | None,
) -> dict[str, Any]:
    retry = _summary(retry_handoff_summary)
    candidates = []
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
    selected_lane_label = _text(retry.get("selected_manual_retry_lane_label"))
    selected_target = _text(retry.get("selected_manual_retry_target_id"))
    selected_shard = _text(retry.get("selected_manual_retry_shard_id"))
    selected_kind = _text(retry.get("selected_manual_retry_selected_command_kind"))
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
    focus_target = _text(retry.get("manual_retry_focus_target_id"), retry.get("guard_blocked_target_id"))
    if focus_target:
        for payload in candidates:
            if _text(_summary(payload).get("target_id")) == focus_target:
                return payload
    return candidates[0] if candidates else {}


def _manual_retry_next_step(
    retry_handoff_summary: dict[str, Any] | None,
    *lane_payloads: dict[str, Any] | None,
) -> str:
    selected_lane = _select_manual_retry_lane(retry_handoff_summary, *lane_payloads)
    lane_step = _manual_retry_next_step_from_lane(selected_lane)
    if lane_step:
        return lane_step
    retry = _summary(retry_handoff_summary)
    return _text(retry.get("current_results_next_required_step"), retry.get("next_required_step"))


def _selected_lane_counts_as_actionable(lane_payload: dict[str, Any] | None) -> bool:
    lane = _summary(lane_payload)
    lane_label = _text(lane.get("followup_lane_label"), lane.get("lane_label"))
    status = _text(lane.get("status"))
    return bool(lane.get("ready_for_manual_retry", False)) or (
        lane_label == "exploratory_gate4.5_followup" and status.startswith("wetlab_stk17b_exploratory_followup_lane_")
    ) or (
        status.startswith("wetlab_lbdhodh_exploratory_retry_lane_")
        and _text(lane.get("queue_status")) == "running"
        and bool(_text(lane.get("next_required_step")))
    )


def _stk17b_followup_review_next_step(review_surface: dict[str, Any] | None) -> str:
    review = _summary(review_surface)
    if _text(review.get("target_id")) != "STK17B (DRAK2)":
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


def _tcruzi_pde_rescue_only_branch_next_step(branch_summary_payload: dict[str, Any] | None) -> str:
    branch = _summary(branch_summary_payload)
    if _text(branch.get("target_id")) != "T. cruzi PDE":
        return ""
    if not _text(branch.get("branch_state")):
        return ""
    return _text(branch.get("next_required_step"))


def _build_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    rows = payload.get("rows", []) or []
    sections = payload.get("sections", {}) or {}

    lines: list[str] = [f"# {payload.get('title', 'Wet-Lab Monitor Semantics')}", ""]
    lines.extend([
        "## Current Semantics",
        "",
        f"- resolved_shards: `{s['resolved_shards']}`",
        f"- successful_resolved_shards: `{s['successful_resolved_shards']}`",
        f"- held_resolved_shards: `{s['held_resolved_shards']}`",
        f"- successful_share: `{s['successful_share_pct']}%`",
        f"- held_share: `{s['held_share_pct']}%`",
        f"- primary_success_rate: `{s['primary_success_rate_shards_per_hour']:.2f}/h`",
        f"- primary_hold_rate: `{s['primary_hold_rate_shards_per_hour']:.2f}/h`",
        f"- counter_success_rate: `{s['counter_success_rate_shards_per_hour']:.2f}/h`",
        f"- counter_hold_rate: `{s['counter_hold_rate_shards_per_hour']:.2f}/h`",
        f"- why_fast_note: `{s['why_fast_note']}`",
        f"- guard_note: `{s['guard_note']}`",
        f"- selected_manual_retry_lane_label: `{s['selected_manual_retry_lane_label']}`",
        f"- selected_manual_retry_freeze_state: `{s['selected_manual_retry_freeze_state']}`",
        f"- selected_manual_retry_freeze_note: `{s['selected_manual_retry_freeze_note']}`",
        f"- stk17b_followup_lane_label: `{s['stk17b_followup_lane_label']}`",
        f"- stk17b_followup_freeze_state: `{s['stk17b_followup_freeze_state']}`",
        f"- stk17b_followup_freeze_note: `{s['stk17b_followup_freeze_note']}`",
        f"- stk17b_followup_followup_shard_ids: `{s['stk17b_followup_followup_shard_ids']}`",
        f"- hard_target_rescue_lane_lane_label: `{s['hard_target_rescue_lane_lane_label']}`",
        f"- rescue_anchor_target_id: `{s['rescue_anchor_target_id']}`",
        f"- rescue_three_bead_candidate_target_id: `{s['rescue_three_bead_candidate_target_id']}`",
    ])

    lines.extend([
        "",
        "## Meaning",
        "",
        "- `resolved` means a row left the unresolved pool. It includes both `result_ready` rows and `explicit_hold` rows.",
        "- `successful_resolved` means the row completed with a usable result (`result_ready`).",
        "- `held_resolved` means the row was resolved by guard logic but did not produce a usable result (`explicit_hold`).",
        "- Do not treat `resolved` alone as scientific throughput. In this pipeline, hold rows are intentionally counted as resolved to keep the queue moving, which can make progress look fast even when the science output is weak.",
    ])

    lines.extend([
        "",
        "## Rate Interpretation",
        "",
        f"- primary success rate: `{_format_rate_label(s['primary_success_rate_shards_per_hour'])}` based on median successful shard runtime (`{s['primary_success_runtime_median_minutes']}m`).",
        f"- primary recent success rate: `{_format_rate_label(s['primary_recent_success_rate_shards_per_hour'])}` based on recent median successful shard runtime (`{s['primary_success_runtime_recent_median_minutes']}m`).",
        f"- primary hold rate: `{_format_rate_label(s['primary_hold_rate_shards_per_hour'])}` based on hold runtime median (`{s['primary_hold_runtime_median_minutes']}m`).",
        f"- counterscreen success rate: `{_format_rate_label(s['counter_success_rate_shards_per_hour'])}` when counterscreen rows actually complete with results.",
        f"- counterscreen hold rate: `{_format_rate_label(s['counter_hold_rate_shards_per_hour'])}` when counterscreen rows are consumed by guards or pauses.",
        "- If `resolved` climbs faster than `successful_resolved`, the runbook is showing guard churn rather than scientific throughput.",
        "- If `signal_age` is small but rate is low, the lane is alive but spending time in holds or gate failures.",
    ])

    lines.extend([
        "",
        "## Why It Can Look Fast",
        "",
        "- The watcher can auto-resolve failures quickly, so `resolved` increases even when result quality does not.",
        "- Success rows and hold rows are now split; the gap between them is the first thing to check when progress looks suspiciously fast.",
        "- A target with repeated stage1 or stage6 failures can cycle through many rows without adding much successful evidence.",
        f"- Current split is `{s['successful_resolved_shards']}` successful vs `{s['held_resolved_shards']}` held, so most of the resolved volume is guard-driven rather than success-driven.",
    ])

    lines.extend([
        "",
        "## Guard Checklist",
        "",
        "1. Check `runs/wetlab_primary_stage6_failure_surface_current.json` for repeated stage1 mapping or stage6 gate failures.",
        "2. Check `runs/wetlab_broad_screen_execution_queue_current.json` and `runs/wetlab_broad_screen_antitarget_execution_queue_current.json` for `explicit_hold`, `stale_running`, or `running_supervision_only` rows.",
        "3. Check the per-shard throughput summary JSON for the failing target/shard to see whether `stage1_ligand_mapping` or `stage6_operational_gate` failed.",
        "4. If the guard fired because of consecutive auto-holds, stop auto-start for that target until the mapping contract or gate preset is corrected.",
        "5. If counterscreen is compute-attached, inspect its live watcher state before assuming it is supervision-only.",
    ])

    lines.extend([
        "",
        "## Current Guard Surface",
        "",
        f"- guard targets: `{s['guard_targets']}`",
        f"- guard threshold: `{s['guard_hold_limit']}` consecutive auto-holds",
        f"- guard active: `{s['guard_active']}`",
        f"- guard blocked target: `{s['guard_blocked_target_id']}`",
        f"- guard hold streak: `{s['guard_hold_streak']}`",
        f"- failure surface artifact: `runs/wetlab_primary_stage6_failure_surface_current.md`",
    ])

    if sections:
        lines.extend(["", "## Structured", ""])
        for key, value in sections.items():
            lines.append(f"- {key}: `{value}`")

    if rows:
        lines.extend(["", "## Rows", "", "| topic | value | details |", "| --- | --- | --- |"])
        for row in rows:
            lines.append(f"| {row.get('topic','')} | {row.get('value','')} | {row.get('details','')} |")

    lines.extend([
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ])
    return "\n".join(lines)


def build_payload(
    precision_monitor: dict[str, Any],
    execution_queue: dict[str, Any],
    antitarget_execution_queue: dict[str, Any],
    antitarget_progress: dict[str, Any] | None = None,
    failure_surface: dict[str, Any] | None = None,
    retry_handoff_summary: dict[str, Any] | None = None,
    dpre1_branch_review_surface: dict[str, Any] | None = None,
    dengue_stage6_tuning_surface: dict[str, Any] | None = None,
    dengue_exploratory_retry_lane: dict[str, Any] | None = None,
    lbdhodh_stage6_tuning_surface: dict[str, Any] | None = None,
    lbdhodh_exploratory_retry_lane: dict[str, Any] | None = None,
    lbdhodh_gate51_validation_review_surface: dict[str, Any] | None = None,
    tcruzi_pde_rescue_review_surface: dict[str, Any] | None = None,
    tcruzi_pde_promoted_top4_review_packet: dict[str, Any] | None = None,
    tcruzi_pde_rescue_only_branch_summary: dict[str, Any] | None = None,
    stk17b_manual_retry_lane: dict[str, Any] | None = None,
    stk17b_exploratory_followup_lane: dict[str, Any] | None = None,
    stk17b_exploratory_retry_lane: dict[str, Any] | None = None,
    stk17b_followup_review_surface: dict[str, Any] | None = None,
    plpro_manual_retry_lane: dict[str, Any] | None = None,
    kinase_retry_policy_templates: dict[str, Any] | None = None,
    target_retry_policy_templates: dict[str, Any] | None = None,
    mapping_fix_retry_policy_templates: dict[str, Any] | None = None,
    hard_target_rescue_lane: dict[str, Any] | None = None,
    rescue_anchor_artifacts: dict[str, Any] | None = None,
    rescue_three_bead_candidates: dict[str, Any] | None = None,
    tcruzi_krs1_branch_review_surface: dict[str, Any] | None = None,
    selected_allatom_visual_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    monitor_summary = _summary(precision_monitor)
    queue_summary = _summary(execution_queue)
    antitarget_queue_summary = _summary(antitarget_execution_queue)
    antitarget_progress_summary = _summary(antitarget_progress)
    failure_surface_summary = _summary(failure_surface)
    dpre1_branch_review_summary_payload = _dpre1_branch_review_summary(dpre1_branch_review_surface)
    krs1_branch_review_summary_payload = _krs1_branch_review_summary(tcruzi_krs1_branch_review_surface)

    monitor_rows = [dict(row) for row in (precision_monitor.get("rows", []) or [])]
    rates = _current_rates_from_monitor(monitor_summary, monitor_rows)
    counter_rates = _current_rates_from_antitarget_progress(antitarget_progress)

    resolved_shards = _safe_int(monitor_summary.get("resolved_shards", queue_summary.get("resolved_row_count", 0)), 0)
    successful_resolved_shards = _safe_int(monitor_summary.get("successful_resolved_shards", 0), 0)
    held_resolved_shards = _safe_int(monitor_summary.get("held_resolved_shards", 0), 0)
    total_shards = _safe_int(monitor_summary.get("total_shards", queue_summary.get("queue_row_count", 0)), 0)
    successful_share_pct = _percent(successful_resolved_shards, resolved_shards)
    held_share_pct = _percent(held_resolved_shards, resolved_shards)

    primary_focus = str(monitor_summary.get("focus_target_id", "")).strip()
    primary_focus_shard = str(monitor_summary.get("focus_shard_id", "")).strip()
    primary_focus_status = str(monitor_summary.get("focus_queue_status", "")).strip()
    counter_primary = str(antitarget_queue_summary.get("first_actionable_primary_target_id", "")).strip()
    counter_anti = str(antitarget_queue_summary.get("first_actionable_anti_target_id", "")).strip()
    counter_shard = str(antitarget_queue_summary.get("first_actionable_shard_id", "")).strip()
    counter_status = str(antitarget_queue_summary.get("first_actionable_queue_status", "")).strip()

    guard_hold_limit = _safe_int(failure_surface_summary.get("guard_hold_limit", 3), 3)
    guard_active = bool(_safe_int(failure_surface_summary.get("auto_hold_row_count", 0), 0) >= guard_hold_limit)
    guard_blocked_target = primary_focus if guard_active and primary_focus else str(failure_surface_summary.get("guard_blocked_target_id", "")).strip()
    guard_hold_streak = _safe_int(failure_surface_summary.get("guard_hold_streak", guard_hold_limit if guard_active else 0), guard_hold_limit if guard_active else 0)
    retry_handoff_summary_payload = _summary(retry_handoff_summary)
    dengue_stage6_summary_payload = _dengue_stage6_summary(
        execution_queue,
        dengue_stage6_tuning_surface,
        dengue_exploratory_retry_lane,
    )
    lbdhodh_stage6_tuning_surface_payload = _summary(lbdhodh_stage6_tuning_surface)
    lbdhodh_exploratory_retry_lane_payload = _summary(lbdhodh_exploratory_retry_lane)
    lbdhodh_gate51_validation_review_surface_payload = _summary(lbdhodh_gate51_validation_review_surface)
    tcruzi_pde_rescue_review_surface_payload = _summary(tcruzi_pde_rescue_review_surface)
    tcruzi_pde_promoted_top4_review_packet_payload = _summary(tcruzi_pde_promoted_top4_review_packet)
    tcruzi_pde_rescue_only_branch_summary_payload = _summary(tcruzi_pde_rescue_only_branch_summary)
    stk17b_manual_retry_lane_payload = _summary(stk17b_manual_retry_lane)
    stk17b_exploratory_followup_lane_payload = _summary(stk17b_exploratory_followup_lane)
    stk17b_exploratory_retry_lane_payload = _summary(stk17b_exploratory_retry_lane)
    stk17b_followup_review_summary = _summary(stk17b_followup_review_surface)
    plpro_manual_retry_lane_payload = _summary(plpro_manual_retry_lane)
    kinase_retry_policy_templates_summary = _summary(kinase_retry_policy_templates)
    target_retry_policy_templates_summary = _summary(target_retry_policy_templates)
    mapping_fix_retry_policy_templates_summary = _summary(mapping_fix_retry_policy_templates)
    hard_target_rescue_lane_payload = _hard_target_rescue_lane_summary(hard_target_rescue_lane)
    rescue_anchor_artifacts_payload = _rescue_anchor_artifacts_summary(rescue_anchor_artifacts)
    rescue_three_bead_candidates_payload = _rescue_three_bead_candidates_summary(rescue_three_bead_candidates)
    stage6_retry_policy_templates_summary = _stage6_retry_template_summary(target_retry_policy_templates)
    selected_manual_retry_lane = _select_manual_retry_lane(
        retry_handoff_summary,
        lbdhodh_exploratory_retry_lane,
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
    )
    selected_manual_retry_lane_payload = _summary(selected_manual_retry_lane)
    manual_retry_step = _manual_retry_next_step(
        retry_handoff_summary,
        lbdhodh_exploratory_retry_lane,
        stk17b_exploratory_followup_lane,
        stk17b_exploratory_retry_lane,
        stk17b_manual_retry_lane,
        plpro_manual_retry_lane,
    )
    stk17b_followup_review_next_step = _stk17b_followup_review_next_step(stk17b_followup_review_surface)
    tcruzi_pde_rescue_review_next_step = _tcruzi_pde_rescue_review_next_step(tcruzi_pde_rescue_review_surface)
    tcruzi_pde_rescue_branch_next_step = _tcruzi_pde_rescue_only_branch_next_step(
        tcruzi_pde_rescue_only_branch_summary
    )
    tcruzi_pde_promoted_top4_gate = _gate_state(
        tcruzi_pde_promoted_top4_review_packet_payload,
        operator_ready_keys=("packet_ready_for_operator_review", "packet_ready"),
        wetlab_gate_keys=("wetlab_gate_pass", "packet_ready"),
        final_gate_keys=("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
        claim_available_keys=("claim_gate_available",),
        claim_ready_keys=("claim_ready_for_allatom",),
        legacy_ready=_text(tcruzi_pde_promoted_top4_review_packet_payload.get("status"))
        == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
    )
    tcruzi_pde_rescue_branch_gate = _gate_state(
        tcruzi_pde_rescue_only_branch_summary_payload,
        operator_ready_keys=(
            "branch_ready_for_operator_review",
            "review_packet_ready_for_operator_review",
            "review_packet_ready",
            "promoted_top4_packet_ready",
        ),
        wetlab_gate_keys=(
            "review_packet_wetlab_gate_pass",
            "wetlab_gate_pass",
            "review_packet_ready",
            "promoted_top4_packet_ready",
        ),
        final_gate_keys=(
            "branch_ready_for_final_wetlab",
            "review_packet_final_gate_pass",
            "wetlab_final_gate_pass",
            "review_packet_wetlab_gate_pass",
            "wetlab_gate_pass",
            "review_packet_ready",
            "promoted_top4_packet_ready",
        ),
        claim_available_keys=("review_packet_claim_gate_available", "claim_gate_available"),
        claim_ready_keys=("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
        legacy_ready=_text(tcruzi_pde_rescue_only_branch_summary_payload.get("status"))
        == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
    )
    selected_rescue_operator_gate = _gate_state(
        retry_handoff_summary_payload,
        operator_ready_keys=(
            "selected_rescue_branch_operator_packet_ready_for_operator_review",
            "tcruzi_pde_rescue_operator_packet_ready_for_operator_review",
            "selected_rescue_branch_operator_packet_ready",
            "tcruzi_pde_rescue_operator_packet_ready",
        ),
        wetlab_gate_keys=(
            "selected_rescue_branch_operator_packet_wetlab_gate_pass",
            "tcruzi_pde_rescue_operator_packet_wetlab_gate_pass",
            "selected_rescue_branch_operator_packet_ready",
            "tcruzi_pde_rescue_operator_packet_ready",
        ),
        final_gate_keys=(
            "selected_rescue_branch_operator_packet_final_gate_pass",
            "tcruzi_pde_rescue_operator_packet_final_gate_pass",
            "selected_rescue_branch_operator_packet_wetlab_gate_pass",
            "tcruzi_pde_rescue_operator_packet_wetlab_gate_pass",
            "selected_rescue_branch_operator_packet_ready",
            "tcruzi_pde_rescue_operator_packet_ready",
        ),
        claim_available_keys=(
            "selected_rescue_branch_operator_packet_claim_gate_available",
            "tcruzi_pde_rescue_operator_packet_claim_gate_available",
        ),
        claim_ready_keys=(
            "selected_rescue_branch_operator_packet_claim_ready_for_allatom",
            "tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom",
        ),
        legacy_ready=bool(retry_handoff_summary_payload.get("selected_rescue_branch_operator_packet_ready", False)),
    )
    selected_allatom_surface_label = _text(
        retry_handoff_summary_payload.get("selected_allatom_surface_label"),
        retry_handoff_summary_payload.get("allatom_family_focus_surface_label"),
    )
    selected_allatom_has_reported_gate_fields = any(
        key in retry_handoff_summary_payload and retry_handoff_summary_payload.get(key) not in {"", None}
        for key in (
            "selected_allatom_packet_ready_for_operator_review",
            "selected_allatom_operator_review_ready",
            "selected_allatom_wetlab_gate_pass",
            "selected_allatom_wetlab_final_gate_pass",
            "selected_allatom_claim_gate_available",
            "selected_allatom_claim_ready_for_allatom",
            "allatom_family_focus_packet_ready_for_operator_review",
            "allatom_family_focus_operator_review_ready",
            "allatom_family_focus_wetlab_gate_pass",
            "allatom_family_focus_wetlab_final_gate_pass",
            "allatom_family_focus_claim_gate_available",
            "allatom_family_focus_claim_ready_for_allatom",
        )
    )
    selected_allatom_legacy_operator_ready = bool(
        bool(retry_handoff_summary_payload.get("allatom_family_ready", False))
        and selected_allatom_surface_label.endswith("review_packet")
    )
    selected_allatom_gate = _gate_state(
        retry_handoff_summary_payload,
        operator_ready_keys=(
            "selected_allatom_packet_ready_for_operator_review",
            "selected_allatom_operator_review_ready",
            "allatom_family_focus_packet_ready_for_operator_review",
            "allatom_family_focus_operator_review_ready",
        ),
        wetlab_gate_keys=(
            "selected_allatom_wetlab_gate_pass",
            "allatom_family_focus_wetlab_gate_pass",
        ),
        final_gate_keys=(
            "selected_allatom_wetlab_final_gate_pass",
            "allatom_family_focus_wetlab_final_gate_pass",
        ),
        claim_available_keys=(
            "selected_allatom_claim_gate_available",
            "allatom_family_focus_claim_gate_available",
        ),
        claim_ready_keys=(
            "selected_allatom_claim_ready_for_allatom",
            "allatom_family_focus_claim_ready_for_allatom",
        ),
        legacy_ready=selected_allatom_legacy_operator_ready,
        legacy_wetlab_ready=False,
        legacy_final_ready=False,
    )
    selected_allatom_operator_ready_source = _text(
        retry_handoff_summary_payload.get("selected_allatom_packet_ready_for_operator_review_source"),
        retry_handoff_summary_payload.get("selected_allatom_operator_review_ready_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_packet_ready_for_operator_review_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_operator_review_ready_source"),
        selected_allatom_gate.get("packet_ready_for_operator_review_source"),
    )
    selected_allatom_wetlab_gate_source = _text(
        retry_handoff_summary_payload.get("selected_allatom_wetlab_gate_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_wetlab_gate_source"),
        selected_allatom_gate.get("wetlab_gate_source"),
    )
    selected_allatom_final_gate_source = _text(
        retry_handoff_summary_payload.get("selected_allatom_wetlab_final_gate_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_wetlab_final_gate_source"),
        selected_allatom_gate.get("wetlab_final_gate_source"),
    )
    selected_allatom_claim_gate_source = _text(
        retry_handoff_summary_payload.get("selected_allatom_claim_gate_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_claim_gate_source"),
        selected_allatom_gate.get("claim_gate_source"),
    )
    selected_allatom_claim_ready_source = _text(
        retry_handoff_summary_payload.get("selected_allatom_claim_ready_source"),
        retry_handoff_summary_payload.get("allatom_family_focus_claim_ready_source"),
        selected_allatom_gate.get("claim_ready_source"),
    )
    selected_allatom_gate_source_surface_label = _text(
        retry_handoff_summary_payload.get("selected_allatom_gate_source_surface_label"),
        retry_handoff_summary_payload.get("allatom_family_focus_gate_source_surface_label"),
        selected_allatom_surface_label if selected_allatom_legacy_operator_ready else "",
    )
    selected_allatom_readiness_semantics = _text(
        retry_handoff_summary_payload.get("selected_allatom_readiness_semantics"),
        retry_handoff_summary_payload.get("allatom_family_focus_readiness_semantics"),
        "legacy_review_packet_fallback"
        if selected_allatom_legacy_operator_ready and not selected_allatom_has_reported_gate_fields
        else "not_reported",
    )
    selected_allatom_focus_artifact_json = _selected_allatom_focus_artifact_json_path(
        retry_handoff_summary_payload
    )
    selected_allatom_focus_summary = _load_artifact_summary(selected_allatom_focus_artifact_json)
    selected_allatom_readiness_semantics = _text(
        retry_handoff_summary_payload.get("selected_allatom_readiness_semantics"),
        retry_handoff_summary_payload.get("allatom_family_focus_readiness_semantics"),
        selected_allatom_focus_summary.get("selected_allatom_readiness_semantics"),
        "legacy_review_packet_fallback"
        if selected_allatom_legacy_operator_ready and not selected_allatom_has_reported_gate_fields
        else "not_reported",
    )
    selected_allatom_claim_gate_source = _text(
        selected_allatom_focus_summary.get("selected_allatom_claim_gate_source"),
        retry_handoff_summary_payload.get("selected_allatom_claim_gate_source"),
        selected_allatom_gate.get("claim_gate_source"),
    )
    selected_allatom_claim_ready_source = _text(
        selected_allatom_focus_summary.get("selected_allatom_claim_ready_source"),
        retry_handoff_summary_payload.get("selected_allatom_claim_ready_source"),
        selected_allatom_gate.get("claim_ready_source"),
    )
    selected_allatom_actions_value = retry_handoff_summary_payload.get(
        "selected_allatom_commercial_primary_upgrade_actions_v1"
    )
    if selected_allatom_actions_value is None or selected_allatom_actions_value == "":
        selected_allatom_actions_value = retry_handoff_summary_payload.get(
            "allatom_family_focus_commercial_primary_upgrade_actions_v1"
        )
    if selected_allatom_actions_value is None or selected_allatom_actions_value == "":
        selected_allatom_actions_value = selected_allatom_focus_summary.get(
            "commercial_primary_upgrade_actions_v1"
        )
    selected_allatom_commercial_actions = _normalize_string_list(selected_allatom_actions_value)
    selected_allatom_commercial_reported = bool(
        _text(
            retry_handoff_summary_payload.get("selected_allatom_commercial_schema_version"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_schema_version"),
            selected_allatom_focus_summary.get("commercial_schema_version"),
            selected_allatom_focus_summary.get("commercial_schema_version_v1"),
            retry_handoff_summary_payload.get("selected_allatom_commercial_risk_bucket_v1"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_risk_bucket_v1"),
            selected_allatom_focus_summary.get("commercial_risk_bucket_v1"),
            retry_handoff_summary_payload.get("selected_allatom_commercial_decision_class_v1"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_decision_class_v1"),
            selected_allatom_focus_summary.get("commercial_decision_class_v1"),
        )
        or (
            retry_handoff_summary_payload.get("selected_allatom_commercial_overall_score_v1") is not None
            and retry_handoff_summary_payload.get("selected_allatom_commercial_overall_score_v1") != ""
        )
        or (
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_overall_score_v1") is not None
            and retry_handoff_summary_payload.get("allatom_family_focus_commercial_overall_score_v1") != ""
        )
        or (
            selected_allatom_focus_summary.get("commercial_overall_score_v1") is not None
            and selected_allatom_focus_summary.get("commercial_overall_score_v1") != ""
        )
        or selected_allatom_commercial_actions
        or retry_handoff_summary_payload.get("selected_allatom_commercial_hard_gate_pass_v1") is not None
        or retry_handoff_summary_payload.get("allatom_family_focus_commercial_hard_gate_pass_v1") is not None
        or selected_allatom_focus_summary.get("commercial_hard_gate_pass_v1") is not None
    )
    selected_allatom_commercial_overall_value = retry_handoff_summary_payload.get(
        "selected_allatom_commercial_overall_score_v1"
    )
    if selected_allatom_commercial_overall_value is None or selected_allatom_commercial_overall_value == "":
        selected_allatom_commercial_overall_value = retry_handoff_summary_payload.get(
            "allatom_family_focus_commercial_overall_score_v1"
        )
    if selected_allatom_commercial_overall_value is None or selected_allatom_commercial_overall_value == "":
        selected_allatom_commercial_overall_value = selected_allatom_focus_summary.get(
            "commercial_overall_score_v1"
        )
    selected_allatom_commercial_overall_score = _safe_float(
        selected_allatom_commercial_overall_value,
        0.0,
    )
    selected_allatom_commercial_risk_bucket = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_risk_bucket_v1"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_risk_bucket_v1"),
        selected_allatom_focus_summary.get("commercial_risk_bucket_v1"),
    )
    selected_allatom_commercial_decision_class = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_decision_class_v1"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_decision_class_v1"),
        selected_allatom_focus_summary.get("commercial_decision_class_v1"),
    )
    selected_allatom_commercial_hard_gate_value = retry_handoff_summary_payload.get(
        "selected_allatom_commercial_hard_gate_pass_v1"
    )
    if selected_allatom_commercial_hard_gate_value is None or selected_allatom_commercial_hard_gate_value == "":
        selected_allatom_commercial_hard_gate_value = retry_handoff_summary_payload.get(
            "allatom_family_focus_commercial_hard_gate_pass_v1"
        )
    if selected_allatom_commercial_hard_gate_value is None or selected_allatom_commercial_hard_gate_value == "":
        selected_allatom_commercial_hard_gate_value = selected_allatom_focus_summary.get(
            "commercial_hard_gate_pass_v1"
        )
    selected_allatom_commercial_hard_gate_pass = bool(_safe_bool(selected_allatom_commercial_hard_gate_value))
    selected_allatom_commercial_actions_text = " | ".join(selected_allatom_commercial_actions)
    selected_allatom_commercial_source_surface_label = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_source_surface_label_v1"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_source_surface_label_v1"),
        selected_allatom_surface_label if selected_allatom_focus_summary else "",
    )
    selected_allatom_commercial_actions_v2_value = retry_handoff_summary_payload.get(
        "selected_allatom_commercial_primary_upgrade_actions_v2"
    )
    if selected_allatom_commercial_actions_v2_value is None or selected_allatom_commercial_actions_v2_value == "":
        selected_allatom_commercial_actions_v2_value = retry_handoff_summary_payload.get(
            "allatom_family_focus_commercial_primary_upgrade_actions_v2"
        )
    if selected_allatom_commercial_actions_v2_value is None or selected_allatom_commercial_actions_v2_value == "":
        selected_allatom_commercial_actions_v2_value = selected_allatom_focus_summary.get(
            "commercial_primary_upgrade_actions_v2"
        )
    selected_allatom_commercial_actions_v2 = _normalize_string_list(
        selected_allatom_commercial_actions_v2_value
    )
    selected_allatom_commercial_schema_version_v2 = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_schema_version_v2"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_schema_version_v2"),
        selected_allatom_focus_summary.get("commercial_schema_version_v2"),
    )
    selected_allatom_commercial_hard_gate_value_v2 = retry_handoff_summary_payload.get(
        "selected_allatom_commercial_hard_gate_pass_v2"
    )
    if selected_allatom_commercial_hard_gate_value_v2 is None or selected_allatom_commercial_hard_gate_value_v2 == "":
        selected_allatom_commercial_hard_gate_value_v2 = retry_handoff_summary_payload.get(
            "allatom_family_focus_commercial_hard_gate_pass_v2"
        )
    if selected_allatom_commercial_hard_gate_value_v2 is None or selected_allatom_commercial_hard_gate_value_v2 == "":
        selected_allatom_commercial_hard_gate_value_v2 = selected_allatom_focus_summary.get(
            "commercial_hard_gate_pass_v2"
        )
    selected_allatom_commercial_hard_gate_pass_v2 = bool(
        _safe_bool(selected_allatom_commercial_hard_gate_value_v2)
    )
    selected_allatom_commercial_soft_score_v2 = _safe_float(
        _text(
            retry_handoff_summary_payload.get("selected_allatom_commercial_soft_score_v2"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_soft_score_v2"),
            selected_allatom_focus_summary.get("commercial_soft_score_v2"),
        ),
        0.0,
    )
    selected_allatom_commercial_confidence_score_v2 = _safe_float(
        _text(
            retry_handoff_summary_payload.get("selected_allatom_commercial_confidence_score_v2"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_confidence_score_v2"),
            selected_allatom_focus_summary.get("commercial_confidence_score_v2"),
        ),
        0.0,
    )
    selected_allatom_commercial_overall_score_v2 = _safe_float(
        _text(
            retry_handoff_summary_payload.get("selected_allatom_commercial_overall_score_v2"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_overall_score_v2"),
            selected_allatom_focus_summary.get("commercial_overall_score_v2"),
        ),
        0.0,
    )
    selected_allatom_commercial_risk_bucket_v2 = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_risk_bucket_v2"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_risk_bucket_v2"),
        selected_allatom_focus_summary.get("commercial_risk_bucket_v2"),
    )
    selected_allatom_commercial_decision_class_v2 = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_decision_class_v2"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_decision_class_v2"),
        selected_allatom_focus_summary.get("commercial_decision_class_v2"),
    )
    selected_allatom_commercial_human_summary_v2 = _text(
        retry_handoff_summary_payload.get("selected_allatom_commercial_human_summary_v2"),
        retry_handoff_summary_payload.get("allatom_family_focus_commercial_human_summary_v2"),
        selected_allatom_focus_summary.get("commercial_human_summary_v2"),
    )
    selected_allatom_commercial_reported_v2 = bool(
        selected_allatom_commercial_schema_version_v2
        or (
            retry_handoff_summary_payload.get("selected_allatom_commercial_hard_gate_pass_v2")
            is not None
        )
        or (
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_hard_gate_pass_v2")
            is not None
        )
        or selected_allatom_focus_summary.get("commercial_hard_gate_pass_v2") is not None
        or selected_allatom_commercial_soft_score_v2 > 0
        or selected_allatom_commercial_confidence_score_v2 > 0
        or selected_allatom_commercial_overall_score_v2 > 0
        or selected_allatom_commercial_risk_bucket_v2
        or selected_allatom_commercial_decision_class_v2
        or selected_allatom_commercial_actions_v2
        or selected_allatom_commercial_human_summary_v2
    )
    selected_allatom_commercial_actions_text_v2 = " | ".join(selected_allatom_commercial_actions_v2)
    selected_allatom_translation_gate_status = _text(
        retry_handoff_summary_payload.get("selected_allatom_translation_gate_status"),
        retry_handoff_summary_payload.get("allatom_family_focus_translation_gate_status"),
        selected_allatom_focus_summary.get("translation_gate_focus_status"),
    )
    selected_allatom_translation_gate_score_value = retry_handoff_summary_payload.get(
        "selected_allatom_translation_gate_score"
    )
    if selected_allatom_translation_gate_score_value is None or selected_allatom_translation_gate_score_value == "":
        selected_allatom_translation_gate_score_value = retry_handoff_summary_payload.get(
            "allatom_family_focus_translation_gate_score"
        )
    if selected_allatom_translation_gate_score_value is None or selected_allatom_translation_gate_score_value == "":
        selected_allatom_translation_gate_score_value = selected_allatom_focus_summary.get(
            "translation_gate_focus_score"
        )
    selected_allatom_translation_gate_score = _safe_float(
        selected_allatom_translation_gate_score_value,
        0.0,
    )
    selected_allatom_translation_gate_reason = _text(
        retry_handoff_summary_payload.get("selected_allatom_translation_gate_reason"),
        retry_handoff_summary_payload.get("allatom_family_focus_translation_gate_reason"),
        selected_allatom_focus_summary.get("translation_gate_focus_reason"),
    )
    selected_allatom_focus_shortlist_tier = _text(
        retry_handoff_summary_payload.get("selected_allatom_focus_shortlist_tier"),
        retry_handoff_summary_payload.get("allatom_family_focus_shortlist_tier"),
        selected_allatom_focus_summary.get("focus_shortlist_tier"),
    )
    selected_allatom_recommended_next_expensive_lane = _text(
        retry_handoff_summary_payload.get("selected_allatom_recommended_next_expensive_lane"),
        retry_handoff_summary_payload.get("allatom_family_focus_recommended_next_expensive_lane"),
        selected_allatom_focus_summary.get("recommended_next_expensive_lane"),
    )
    selected_allatom_recommended_next_expensive_lane_reason = _text(
        retry_handoff_summary_payload.get("selected_allatom_recommended_next_expensive_lane_reason"),
        retry_handoff_summary_payload.get("allatom_family_focus_recommended_next_expensive_lane_reason"),
        selected_allatom_focus_summary.get("recommended_next_expensive_lane_reason"),
    )
    selected_allatom_translation_reported = bool(
        selected_allatom_translation_gate_status
        or selected_allatom_translation_gate_reason
        or selected_allatom_focus_shortlist_tier
        or selected_allatom_recommended_next_expensive_lane
        or selected_allatom_translation_gate_score_value not in {"", None}
    )
    selected_allatom_translation_human_summary = _text(
        retry_handoff_summary_payload.get("selected_allatom_translation_human_summary"),
        retry_handoff_summary_payload.get("allatom_family_focus_translation_human_summary"),
    )
    if not selected_allatom_translation_human_summary and selected_allatom_translation_reported:
        translation_parts: list[str] = []
        if selected_allatom_translation_gate_status:
            translation_parts.append(f"translation {selected_allatom_translation_gate_status}")
        if selected_allatom_translation_gate_score_value not in {"", None}:
            translation_parts.append(f"score {selected_allatom_translation_gate_score:.1f}")
        if selected_allatom_focus_shortlist_tier:
            translation_parts.append(f"tier {selected_allatom_focus_shortlist_tier}")
        if selected_allatom_recommended_next_expensive_lane:
            translation_parts.append(f"lane {selected_allatom_recommended_next_expensive_lane}")
        if selected_allatom_recommended_next_expensive_lane_reason:
            translation_parts.append(selected_allatom_recommended_next_expensive_lane_reason)
        elif selected_allatom_translation_gate_reason:
            translation_parts.append(selected_allatom_translation_gate_reason)
        selected_allatom_translation_human_summary = " | ".join(
            part for part in translation_parts if part
        )
    selected_allatom_actionability_status = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_status"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_status"),
    )
    selected_allatom_actionability_brief_summary = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_brief_summary"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_brief_summary"),
    )
    selected_allatom_actionability_human_summary = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_human_summary"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_human_summary"),
    )
    selected_allatom_actionability_block_reason = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_block_reason"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_block_reason"),
    )
    selected_allatom_actionability_required_calculations_text = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_required_calculations_text"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_required_calculations_text"),
    )
    selected_allatom_actionability_action_list_text = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_action_list_text"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_action_list_text"),
    )
    selected_allatom_actionability_claim_requirement_mode = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_claim_requirement_mode"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_claim_requirement_mode"),
    )
    selected_allatom_actionability_claim_requirement_status = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_claim_requirement_status"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_claim_requirement_status"),
    )
    selected_allatom_actionability_claim_requirement_reason = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_claim_requirement_reason"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_claim_requirement_reason"),
    )
    selected_allatom_actionability_next_expensive_lane = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_next_expensive_lane"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_next_expensive_lane"),
    )
    selected_allatom_actionability_next_expensive_lane_reason = _text(
        selected_allatom_focus_summary.get("selected_allatom_actionability_next_expensive_lane_reason"),
        retry_handoff_summary_payload.get("selected_allatom_actionability_next_expensive_lane_reason"),
    )
    if not (
        selected_allatom_actionability_status
        or selected_allatom_actionability_human_summary
        or selected_allatom_actionability_brief_summary
        or selected_allatom_actionability_block_reason
        or selected_allatom_actionability_required_calculations_text
        or selected_allatom_actionability_action_list_text
        or selected_allatom_actionability_claim_requirement_mode
        or selected_allatom_actionability_next_expensive_lane
    ):
        selected_allatom_actionability_fallback = _selected_allatom_actionability_fallback(
            final_gate_pass=bool(selected_allatom_gate.get("wetlab_final_gate_pass", False)),
            operator_review_ready=bool(selected_allatom_gate.get("packet_ready_for_operator_review", False)),
            commercial_hard_gate_blocked=bool(
                (selected_allatom_commercial_reported and not selected_allatom_commercial_hard_gate_pass)
                or (selected_allatom_commercial_reported_v2 and not selected_allatom_commercial_hard_gate_pass_v2)
            ),
            claim_gate_available=bool(selected_allatom_gate.get("claim_gate_available", False)),
            claim_ready_for_allatom=bool(selected_allatom_gate.get("claim_ready_for_allatom", False)),
            translation_status=selected_allatom_translation_gate_status,
            translation_reason=selected_allatom_translation_gate_reason,
            shortlist_tier=selected_allatom_focus_shortlist_tier,
            next_expensive_lane=selected_allatom_recommended_next_expensive_lane,
            next_expensive_lane_reason=selected_allatom_recommended_next_expensive_lane_reason,
            next_required_step=_text(
                retry_handoff_summary_payload.get("selected_allatom_next_required_step"),
                selected_allatom_focus_summary.get("next_required_step"),
            ),
        )
        selected_allatom_actionability_status = _text(
            selected_allatom_actionability_status,
            selected_allatom_actionability_fallback.get("status"),
        )
        selected_allatom_actionability_brief_summary = _text(
            selected_allatom_actionability_brief_summary,
            selected_allatom_actionability_fallback.get("brief_summary"),
        )
        selected_allatom_actionability_human_summary = _text(
            selected_allatom_actionability_human_summary,
            selected_allatom_actionability_fallback.get("human_summary"),
        )
        selected_allatom_actionability_block_reason = _text(
            selected_allatom_actionability_block_reason,
            selected_allatom_actionability_fallback.get("block_reason"),
        )
        selected_allatom_actionability_required_calculations_text = _text(
            selected_allatom_actionability_required_calculations_text,
            selected_allatom_actionability_fallback.get("required_calculations_text"),
        )
        selected_allatom_actionability_action_list_text = _text(
            selected_allatom_actionability_action_list_text,
            selected_allatom_actionability_fallback.get("action_list_text"),
        )
        selected_allatom_actionability_claim_requirement_mode = _text(
            selected_allatom_actionability_claim_requirement_mode,
            selected_allatom_actionability_fallback.get("claim_requirement_mode"),
        )
        selected_allatom_actionability_claim_requirement_status = _text(
            selected_allatom_actionability_claim_requirement_status,
            selected_allatom_actionability_fallback.get("claim_requirement_status"),
        )
        selected_allatom_actionability_claim_requirement_reason = _text(
            selected_allatom_actionability_claim_requirement_reason,
            selected_allatom_actionability_fallback.get("claim_requirement_reason"),
        )
        selected_allatom_actionability_next_expensive_lane = _text(
            selected_allatom_actionability_next_expensive_lane,
            selected_allatom_actionability_fallback.get("next_expensive_lane"),
        )
        selected_allatom_actionability_next_expensive_lane_reason = _text(
            selected_allatom_actionability_next_expensive_lane_reason,
            selected_allatom_actionability_fallback.get("next_expensive_lane_reason"),
        )
    selected_allatom_actionability_display = _text(
        selected_allatom_actionability_human_summary,
        selected_allatom_actionability_brief_summary,
        f"lane {selected_allatom_actionability_next_expensive_lane}" if selected_allatom_actionability_next_expensive_lane else "",
    )
    selected_allatom_claim_gate_source = _text(
        selected_allatom_focus_summary.get("selected_allatom_claim_gate_source"),
        retry_handoff_summary_payload.get("selected_allatom_claim_gate_source"),
        selected_allatom_gate.get("claim_gate_source"),
    )
    selected_allatom_claim_gate_policy_version = _text(
        selected_allatom_focus_summary.get("selected_allatom_claim_gate_policy_version"),
        retry_handoff_summary_payload.get("selected_allatom_claim_gate_policy_version"),
    )
    selected_allatom_claim_pass_core_gate = selected_allatom_focus_summary.get("selected_allatom_claim_pass_core_gate")
    selected_allatom_claim_core_failed_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_claim_core_failed_metrics")
    )
    selected_allatom_claim_core_missing_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_claim_core_missing_metrics")
    )
    selected_allatom_claim_failed_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_claim_failed_metrics")
    )
    selected_allatom_claim_missing_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_claim_missing_metrics")
    )
    selected_allatom_translation_gate_v2_failed_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_translation_gate_v2_failed_metrics")
    )
    selected_allatom_translation_gate_v2_missing_metrics = _normalize_string_list(
        selected_allatom_focus_summary.get("selected_allatom_translation_gate_v2_missing_metrics")
    )
    selected_allatom_translation_gate_v2_thresholds = dict(
        selected_allatom_focus_summary.get("selected_allatom_translation_gate_v2_thresholds", {}) or {}
    )
    selected_allatom_canonical = resolve_selected_allatom_canonical(
        review_packet_summary=selected_allatom_focus_summary,
        retry_handoff_summary=retry_handoff_summary_payload,
        next_required_step=_text(
            retry_handoff_summary_payload.get("selected_allatom_next_required_step"),
            selected_allatom_focus_summary.get("next_required_step"),
        ),
    )
    selected_allatom_visual = resolve_selected_allatom_visual_bundle(
        selected_allatom_visual_bundle
    )
    selected_allatom_visual_fields = selected_allatom_visual_surface_fields(
        selected_allatom_visual
    )
    selected_allatom_commercial_schema_version_v2 = _text(
        selected_allatom_canonical.get("commercial_schema_version_v2"),
        selected_allatom_commercial_schema_version_v2,
    )
    selected_allatom_commercial_hard_gate_pass_v2 = bool(
        selected_allatom_canonical.get(
            "commercial_hard_gate_pass_v2",
            selected_allatom_commercial_hard_gate_pass_v2,
        )
    )
    selected_allatom_commercial_soft_score_v2 = _safe_float(
        selected_allatom_canonical.get("commercial_soft_score_v2"),
        selected_allatom_commercial_soft_score_v2,
    )
    selected_allatom_commercial_confidence_score_v2 = _safe_float(
        selected_allatom_canonical.get("commercial_confidence_score_v2"),
        selected_allatom_commercial_confidence_score_v2,
    )
    selected_allatom_commercial_overall_score_v2 = _safe_float(
        selected_allatom_canonical.get("commercial_overall_score_v2"),
        selected_allatom_commercial_overall_score_v2,
    )
    selected_allatom_commercial_risk_bucket_v2 = _text(
        selected_allatom_canonical.get("commercial_risk_bucket_v2"),
        selected_allatom_commercial_risk_bucket_v2,
    )
    selected_allatom_commercial_decision_class_v2 = _text(
        selected_allatom_canonical.get("commercial_decision_class_v2"),
        selected_allatom_commercial_decision_class_v2,
    )
    selected_allatom_commercial_actions_v2 = list(
        selected_allatom_canonical.get("commercial_primary_upgrade_actions_v2", [])
        or selected_allatom_commercial_actions_v2
    )
    selected_allatom_commercial_actions_text_v2 = " | ".join(
        selected_allatom_commercial_actions_v2
    )
    selected_allatom_commercial_human_summary_v2 = _text(
        selected_allatom_canonical.get("commercial_human_summary_v2"),
        selected_allatom_commercial_human_summary_v2,
    )
    selected_allatom_translation_gate_status = _text(
        selected_allatom_canonical.get("translation_gate_focus_status"),
        selected_allatom_translation_gate_status,
    )
    selected_allatom_translation_gate_score = _safe_float(
        selected_allatom_canonical.get("translation_gate_focus_score"),
        selected_allatom_translation_gate_score,
    )
    selected_allatom_translation_gate_reason = _text(
        selected_allatom_canonical.get("translation_gate_focus_reason"),
        selected_allatom_translation_gate_reason,
    )
    selected_allatom_focus_shortlist_tier = _text(
        selected_allatom_canonical.get("focus_shortlist_tier"),
        selected_allatom_focus_shortlist_tier,
    )
    selected_allatom_recommended_next_expensive_lane = _text(
        selected_allatom_canonical.get("recommended_next_expensive_lane"),
        selected_allatom_recommended_next_expensive_lane,
    )
    selected_allatom_recommended_next_expensive_lane_reason = _text(
        selected_allatom_canonical.get("recommended_next_expensive_lane_reason"),
        selected_allatom_recommended_next_expensive_lane_reason,
    )
    selected_allatom_actionability = dict(
        selected_allatom_canonical.get("effective_actionability", {}) or {}
    )
    selected_allatom_actionability_status = _text(
        selected_allatom_actionability.get("status"),
        selected_allatom_actionability_status,
    )
    selected_allatom_actionability_brief_summary = _text(
        selected_allatom_actionability.get("brief_summary"),
        selected_allatom_actionability_brief_summary,
    )
    selected_allatom_actionability_human_summary = _text(
        selected_allatom_actionability.get("human_summary"),
        selected_allatom_actionability_human_summary,
    )
    selected_allatom_actionability_block_reason = _text(
        selected_allatom_actionability.get("block_reason"),
        selected_allatom_actionability_block_reason,
    )
    selected_allatom_actionability_required_calculations_text = _text(
        selected_allatom_actionability.get("required_calculations_text"),
        selected_allatom_actionability_required_calculations_text,
    )
    selected_allatom_actionability_action_list_text = _text(
        selected_allatom_actionability.get("action_list_text"),
        selected_allatom_actionability_action_list_text,
    )
    selected_allatom_actionability_claim_requirement_mode = _text(
        selected_allatom_actionability.get("claim_requirement_mode"),
        selected_allatom_actionability_claim_requirement_mode,
    )
    selected_allatom_actionability_claim_requirement_status = _text(
        selected_allatom_actionability.get("claim_requirement_status"),
        selected_allatom_actionability_claim_requirement_status,
    )
    selected_allatom_actionability_claim_requirement_reason = _text(
        selected_allatom_actionability.get("claim_requirement_reason"),
        selected_allatom_actionability_claim_requirement_reason,
    )
    selected_allatom_actionability_next_expensive_lane = _text(
        selected_allatom_actionability.get("next_expensive_lane"),
        selected_allatom_actionability_next_expensive_lane,
    )
    selected_allatom_actionability_next_expensive_lane_reason = _text(
        selected_allatom_actionability.get("next_expensive_lane_reason"),
        selected_allatom_actionability_next_expensive_lane_reason,
    )
    selected_allatom_translation_gate_v2_failed_metrics = list(
        selected_allatom_actionability.get("translation_gate_v2_failed_metrics", [])
        or selected_allatom_translation_gate_v2_failed_metrics
    )
    selected_allatom_translation_gate_v2_missing_metrics = list(
        selected_allatom_actionability.get("translation_gate_v2_missing_metrics", [])
        or selected_allatom_translation_gate_v2_missing_metrics
    )
    selected_allatom_translation_gate_v2_thresholds = dict(
        selected_allatom_actionability.get("translation_gate_v2_thresholds", {})
        or selected_allatom_translation_gate_v2_thresholds
    )
    selected_allatom_raw_claim = dict(selected_allatom_canonical.get("raw_claim", {}) or {})
    manual_retry_ready = _selected_lane_counts_as_actionable(selected_manual_retry_lane)
    selected_manual_retry_freeze_state = _text(
        selected_manual_retry_lane_payload.get("hard_freeze_state"),
        selected_manual_retry_lane_payload.get("freeze_state"),
        retry_handoff_summary_payload.get("selected_manual_retry_freeze_state"),
    )
    selected_manual_retry_freeze_note = _text(
        stk17b_followup_review_next_step if _text(retry_handoff_summary_payload.get("selected_manual_retry_lane_label")) == "exploratory_gate4.5_followup" else "",
        selected_manual_retry_lane_payload.get("freeze_note"),
        selected_manual_retry_lane_payload.get("next_required_step"),
        retry_handoff_summary_payload.get("selected_manual_retry_freeze_note"),
        retry_handoff_summary_payload.get("current_results_next_required_step"),
        retry_handoff_summary_payload.get("next_required_step"),
    )
    lbdhodh_gate51_validated = bool(
        _text(lbdhodh_gate51_validation_review_surface_payload.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready"
        and bool(lbdhodh_gate51_validation_review_surface_payload.get("gate51_validated", False))
    )
    lbdhodh_validation_next_step = _text(lbdhodh_gate51_validation_review_surface_payload.get("next_required_step"))
    krs1_branch_review_ready = bool(
        _text(krs1_branch_review_summary_payload.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
    )
    selected_krs1_branch_review_next_step = _text(
        retry_handoff_summary_payload.get("selected_krs1_branch_review_next_required_step"),
        krs1_branch_review_summary_payload.get("next_required_step")
        if krs1_branch_review_ready
        else "",
    )
    if manual_retry_ready:
        primary_focus = _text(
            selected_manual_retry_lane_payload.get("target_id"),
            retry_handoff_summary_payload.get("manual_retry_focus_target_id"),
            primary_focus,
        )
        primary_focus_shard = _text(
            selected_manual_retry_lane_payload.get("shard_id"),
            retry_handoff_summary_payload.get("manual_retry_focus_shard_id"),
            primary_focus_shard,
        )
    guard_targets = "; ".join(
        str(row.get("target_id", "")).strip()
        for row in (failure_surface.get("rows", []) or [])
        if str(row.get("target_id", "")).strip() and not str(row.get("shard_id", "")).strip()
    )
    if not guard_targets:
        guard_targets = "SARS-CoV-2 Mpro; T. cruzi PDE; ALK2"

    primary_success_rate = rates["primary_success_rate_shards_per_hour"]
    primary_hold_rate = rates["primary_hold_rate_shards_per_hour"]
    counter_success_rate = counter_rates["success_rate_shards_per_hour"]
    counter_hold_rate = counter_rates["hold_rate_shards_per_hour"]

    why_fast_note = (
        "resolved counts include hold rows, so progress can jump quickly when guard logic auto-consumes failures"
        if held_resolved_shards > successful_resolved_shards
        else "progress is dominated by successful rows"
    )
    guard_note = (
        f"auto-start is blocked for {guard_blocked_target} after {guard_hold_streak} consecutive auto-holds; {manual_retry_step}"
        if guard_active and guard_blocked_target
        else "no active auto-hold guard is currently blocking a target"
    )
    dpre1_branch_review_ready = bool(
        _text(dpre1_branch_review_summary_payload.get("status")) == "wetlab_dpre1_branch_review_surface_ready"
    )
    dpre1_priority_step = (
        _text(
            dpre1_branch_review_summary_payload.get("exploratory_retry_next_required_step"),
            dpre1_branch_review_summary_payload.get("next_required_step"),
        )
        if dpre1_branch_review_ready
        else ""
    )
    tcruzi_pde_promoted_best_compound_name = _compound_display_name(
        tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
        tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name"),
        tcruzi_pde_promoted_top4_review_packet_payload.get("best_ligand_id"),
    )
    tcruzi_pde_rescue_only_branch_best_compound_name = _compound_display_name(
        tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_human_readable"),
        tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name"),
        tcruzi_pde_rescue_only_branch_summary_payload.get("best_ligand_id"),
    )

    rows = [
        {
            "topic": "resolved",
            "value": str(resolved_shards),
            "details": "Rows that left the unresolved pool, including success and hold rows.",
        },
        {
            "topic": "successful_resolved",
            "value": str(successful_resolved_shards),
            "details": "Resolved rows with a usable result (`result_ready`).",
        },
        {
            "topic": "held_resolved",
            "value": str(held_resolved_shards),
            "details": "Resolved rows consumed by guard logic (`explicit_hold`).",
        },
        {
            "topic": "primary_rate_interpretation",
            "value": _format_rate_label(primary_success_rate),
            "details": f"Success throughput estimate from median successful shard runtime ({monitor_summary.get('median_completed_shard_minutes', 0.0)}m). Hold throughput is {_format_rate_label(primary_hold_rate)}.",
        },
        {
            "topic": "counter_rate_interpretation",
            "value": _format_rate_label(counter_success_rate),
            "details": f"Counterscreen success throughput estimate from antitarget progress runtime. If counterscreen rows are compute-attached, use this as real compute throughput; if the lane is supervision-only, treat it as orchestration pace only. Hold throughput is {_format_rate_label(counter_hold_rate)}.",
        },
        {
            "topic": "why_fast",
            "value": why_fast_note,
            "details": "Resolved counts can rise quickly when auto-holds are being consumed faster than genuine successful results.",
        },
        {
            "topic": "guard_surface",
            "value": guard_note,
            "details": "When the guard fires, inspect the failure surface and the current queue row before restarting auto-start.",
        },
        {
            "topic": "kinase_retry_templates",
            "value": _text(kinase_retry_policy_templates_summary.get("focus_template_label"), "not_ready"),
            "details": (
                f"focus target {_text(kinase_retry_policy_templates_summary.get('focus_target_id')) or '-'} | "
                f"command {_text(kinase_retry_policy_templates_summary.get('focus_selected_command_kind')) or '-'} | "
                f"gate45-only {_safe_int(kinase_retry_policy_templates_summary.get('gate45_only_target_count'), 0)} | "
                f"empirical {_safe_int(kinase_retry_policy_templates_summary.get('empirical_validated_target_count'), 0)}"
            ),
        },
        {
            "topic": "generic_retry_templates",
            "value": _text(target_retry_policy_templates_summary.get("focus_template_label"), "not_ready"),
            "details": (
                f"focus target {_text(target_retry_policy_templates_summary.get('focus_target_id')) or '-'} | "
                f"command {_text(target_retry_policy_templates_summary.get('focus_selected_command_kind')) or '-'} | "
                f"templates {_safe_int(target_retry_policy_templates_summary.get('template_target_count'), 0)} | "
                f"empirical {_safe_int(target_retry_policy_templates_summary.get('empirical_validated_target_count'), 0)}"
            ),
        },
        {
            "topic": "stage6_retry_templates",
            "value": _text(stage6_retry_policy_templates_summary.get("focus_template_label"), "not_ready"),
            "details": (
                f"focus target {_text(stage6_retry_policy_templates_summary.get('focus_target_id')) or '-'} | "
                f"command {_text(stage6_retry_policy_templates_summary.get('focus_selected_command_kind')) or '-'} | "
                f"templates {_safe_int(stage6_retry_policy_templates_summary.get('template_target_count'), 0)} | "
                f"gate4.5 {_safe_int(stage6_retry_policy_templates_summary.get('gate45_candidate_target_count'), 0)} | "
                f"gate5.1 {_safe_int(stage6_retry_policy_templates_summary.get('gate51_candidate_target_count'), 0)}"
            ),
        },
        *(
            [
                {
                    "topic": "allatom_family",
                    "value": _text(retry_handoff_summary_payload.get("selected_allatom_target_id"), "not_ready"),
                    "details": (
                        f"surface {_text(retry_handoff_summary_payload.get('selected_allatom_surface_label')) or '-'} | "
                        f"cmd {_text(retry_handoff_summary_payload.get('selected_allatom_selected_command_kind')) or '-'} | "
                        f"best {_safe_float(retry_handoff_summary_payload.get('selected_allatom_best_mean_min_distance_A'), 0.0):.3f}A | "
                        f"under {_safe_int(retry_handoff_summary_payload.get('selected_allatom_under_2p5_candidate_count'), 0)} | "
                        f"near {_safe_int(retry_handoff_summary_payload.get('selected_allatom_near_candidate_count'), 0)} | "
                        f"scope {_text(retry_handoff_summary_payload.get('selected_allatom_packet_scope')) or '-'} | "
                        f"op_review {str(selected_allatom_gate['packet_ready_for_operator_review']).lower()} | "
                        f"final_gate {str(selected_allatom_gate['wetlab_final_gate_pass']).lower()} | "
                        f"claim {str(selected_allatom_gate['claim_ready_for_allatom']).lower()} | "
                        f"commercial {f'{selected_allatom_commercial_overall_score:.1f}' if selected_allatom_commercial_reported else '-'} | "
                        f"risk {selected_allatom_commercial_risk_bucket or '-'} | "
                        f"decision {selected_allatom_commercial_decision_class or '-'} | "
                        f"commercial_v2 {f'{selected_allatom_commercial_overall_score_v2:.1f}' if selected_allatom_commercial_reported_v2 else '-'} | "
                        f"risk_v2 {selected_allatom_commercial_risk_bucket_v2 or '-'} | "
                        f"decision_v2 {selected_allatom_commercial_decision_class_v2 or '-'} | "
                        f"translation {selected_allatom_translation_gate_status or '-'} | "
                        f"shortlist {selected_allatom_focus_shortlist_tier or '-'} | "
                        f"lane {selected_allatom_recommended_next_expensive_lane or '-'} | "
                        f"actionability {selected_allatom_actionability_brief_summary or '-'} | "
                        f"actions {selected_allatom_commercial_actions_text or '-'} | "
                        f"actions_v2 {selected_allatom_commercial_actions_text_v2 or '-'} | "
                        f"semantics {selected_allatom_readiness_semantics or '-'} | "
                        f"gate_src {selected_allatom_gate_source_surface_label or '-'} | "
                        f"commercial_src {selected_allatom_commercial_source_surface_label or '-'}"
                    ),
                }
            ]
            if bool(retry_handoff_summary_payload.get("allatom_family_ready", False))
            else []
        ),
        *(
            [
                {
                    "topic": "selected_allatom_actionability",
                    "value": selected_allatom_actionability_status or "not_reported",
                    "details": (
                        f"{selected_allatom_actionability_human_summary or '-'} | "
                        f"block {selected_allatom_actionability_block_reason or '-'} | "
                        f"required {selected_allatom_actionability_required_calculations_text or '-'} | "
                        f"lane {selected_allatom_actionability_next_expensive_lane or '-'} | "
                        f"claim {selected_allatom_actionability_claim_requirement_mode or '-'}:{selected_allatom_actionability_claim_requirement_status or '-'} | "
                        f"actions {selected_allatom_actionability_action_list_text or '-'}"
                    ),
                }
            ]
            if bool(selected_allatom_actionability_status or selected_allatom_actionability_human_summary)
            else []
        ),
        *(
            [
                {
                    "topic": "krs1_branch_review",
                    "value": _text(krs1_branch_review_summary_payload.get("branch_label"), "not_ready"),
                    "details": (
                        f"source {_text(krs1_branch_review_summary_payload.get('source_priority')) or '-'} | "
                        f"target {_text(krs1_branch_review_summary_payload.get('target_id')) or '-'} | "
                        f"decision {_text(krs1_branch_review_summary_payload.get('decision_source_priority')) or '-'} | "
                        f"tuning {_safe_float(krs1_branch_review_summary_payload.get('stage6_tuning_recommended_threshold_A'), 0.0):.2f}A | "
                        f"lane {_text(krs1_branch_review_summary_payload.get('exploratory_retry_lane_label')) or '-'} | "
                        f"successor {_text(krs1_branch_review_summary_payload.get('successor_target')) or '-'} | "
                        f"next {_text(selected_krs1_branch_review_next_step, krs1_branch_review_summary_payload.get('next_required_step')) or '-'}"
                    ),
                }
            ]
            if krs1_branch_review_summary_payload
            else []
        ),
        *(
            [
                {
                    "topic": "dpre1_branch_review",
                    "value": _text(dpre1_branch_review_summary_payload.get("branch_label"), "not_ready"),
                    "details": (
                        f"source {_text(dpre1_branch_review_summary_payload.get('source_priority')) or '-'} | "
                        f"target {_text(dpre1_branch_review_summary_payload.get('target_id')) or '-'} | "
                        f"decision {_text(dpre1_branch_review_summary_payload.get('decision_source_priority')) or '-'} | "
                        f"tuning {_safe_float(dpre1_branch_review_summary_payload.get('stage6_tuning_recommended_threshold_A'), 0.0):.2f}A | "
                        f"lane {_text(dpre1_branch_review_summary_payload.get('exploratory_retry_lane_label')) or '-'} | "
                        f"successor {_text(dpre1_branch_review_summary_payload.get('successor_target')) or '-'}"
                    ),
                }
            ]
            if dpre1_branch_review_summary_payload
            else []
        ),
        *(
            [
        {
            "topic": "dengue_stage6_retry",
            "value": _text(dengue_stage6_summary_payload.get("lane_label"), "not_ready"),
            "details": (
                f"source {_text(dengue_stage6_summary_payload.get('source_priority')) or '-'} | "
                f"target {_text(dengue_stage6_summary_payload.get('target_id')) or '-'} | "
                f"threshold {_safe_float(dengue_stage6_summary_payload.get('recommended_threshold_A'), 0.0):.2f}A | "
                f"command {_text(dengue_stage6_summary_payload.get('selected_command_kind')) or '-'} | "
                f"shard {_text(dengue_stage6_summary_payload.get('shard_id')) or '-'}"
            ),
                }
            ]
            if dengue_stage6_summary_payload
            else []
        ),
        {
            "topic": "mapping_fix_retry_templates",
            "value": _text(mapping_fix_retry_policy_templates_summary.get("focus_template_label"), "not_ready"),
            "details": (
                f"focus target {_text(mapping_fix_retry_policy_templates_summary.get('focus_target_id')) or '-'} | "
                f"command {_text(mapping_fix_retry_policy_templates_summary.get('focus_selected_command_kind')) or '-'} | "
                f"ready {_safe_int(mapping_fix_retry_policy_templates_summary.get('ready_target_count'), 0)}/"
                f"{_safe_int(mapping_fix_retry_policy_templates_summary.get('template_target_count'), 0)} | "
                f"targets {_text(mapping_fix_retry_policy_templates_summary.get('ready_targets')) or '-'}"
            ),
        },
        *(
            [
                {
                    "topic": "pde promoted top-4",
                    "value": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("target_id"), "not_ready"),
                    "details": (
                        f"packet {_text(tcruzi_pde_promoted_top4_review_packet_payload.get('packet_scope')) or '-'} | "
                        f"promoted {_safe_int(tcruzi_pde_promoted_top4_review_packet_payload.get('promoted_candidate_count'), 0)} | "
                        f"under2.5 {_safe_int(tcruzi_pde_promoted_top4_review_packet_payload.get('under_2p5_candidate_count'), 0)} | "
                        f"operator_review {str(tcruzi_pde_promoted_top4_gate['packet_ready_for_operator_review']).lower()} | "
                        f"final_gate {str(tcruzi_pde_promoted_top4_gate['wetlab_final_gate_pass']).lower()} | "
                        f"best {tcruzi_pde_promoted_best_compound_name or '-'} @ "
                        f"{_safe_float(tcruzi_pde_promoted_top4_review_packet_payload.get('best_mean_min_distance_A'), 0.0):.3f}A"
                    ),
                }
            ]
            if tcruzi_pde_promoted_top4_review_packet_payload
            else []
        ),
        *(
            [
                {
                    "topic": "pde rescue-only branch",
                    "value": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("branch_label"), "not_ready"),
                    "details": (
                        f"state {_text(tcruzi_pde_rescue_only_branch_summary_payload.get('branch_state')) or '-'} | "
                        f"command {_text(tcruzi_pde_rescue_only_branch_summary_payload.get('selected_command_kind')) or '-'} | "
                        f"promoted {_safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get('promoted_candidate_count'), 0)} | "
                        f"operator_review {str(tcruzi_pde_rescue_branch_gate['packet_ready_for_operator_review']).lower()} | "
                        f"final_gate {str(tcruzi_pde_rescue_branch_gate['wetlab_final_gate_pass']).lower()} | "
                        f"best {tcruzi_pde_rescue_only_branch_best_compound_name or '-'} | "
                        f"default_closed {str(not bool(tcruzi_pde_rescue_only_branch_summary_payload.get('default_lane_reopen_allowed', False))).lower()}"
                    ),
                }
            ]
            if tcruzi_pde_rescue_only_branch_summary_payload
            else []
        ),
        *(
            [
                {
                    "topic": "hard-target rescue",
                    "value": _text(hard_target_rescue_lane_payload.get("lane_label"), "not_ready"),
                    "details": (
                        f"target {_text(hard_target_rescue_lane_payload.get('target_id')) or '-'} | "
                        f"shard {_text(hard_target_rescue_lane_payload.get('shard_id')) or '-'} | "
                        f"stage1_ok={str(bool(hard_target_rescue_lane_payload.get('stage1_ok', False))).lower()} && "
                        f"stage6_fail={str(bool(hard_target_rescue_lane_payload.get('stage6_fail', False))).lower()} | "
                        f"auto_hold_streak {_safe_int(hard_target_rescue_lane_payload.get('auto_hold_streak'), 0)} | "
                        f"rescue eligible {str(bool(hard_target_rescue_lane_payload.get('rescue_eligible', False))).lower()}"
                    ),
                }
            ]
            if hard_target_rescue_lane_payload
            else []
        ),
        *(
            [
                {
                    "topic": "rescue anchors",
                    "value": _text(rescue_anchor_artifacts_payload.get("target_id"), "not_ready"),
                    "details": (
                        f"rescue_only={str(bool(rescue_anchor_artifacts_payload.get('rescue_only', False))).lower()} | "
                        f"anchor_count {_safe_int(rescue_anchor_artifacts_payload.get('anchor_artifact_count'), 0)} | "
                        f"pocket {_text(rescue_anchor_artifacts_payload.get('pocket_anchor_artifact')) or '-'} | "
                        f"native {_text(rescue_anchor_artifacts_payload.get('native_anchor_artifact')) or '-'}"
                    ),
                }
            ]
            if rescue_anchor_artifacts_payload
            else []
        ),
        *(
            [
                {
                    "topic": "3-bead rescue",
                    "value": _text(rescue_three_bead_candidates_payload.get("target_id"), "not_ready"),
                    "details": (
                        f"candidate_count {_safe_int(rescue_three_bead_candidates_payload.get('candidate_count'), 0)} | "
                        f"top-N {_safe_int(rescue_three_bead_candidates_payload.get('top_n'), 0)} | "
                        f"threshold {_safe_float(rescue_three_bead_candidates_payload.get('selected_threshold_A'), 0.0):.2f}A | "
                        f"command {_text(rescue_three_bead_candidates_payload.get('selected_command_kind')) or '-'}"
                    ),
                }
            ]
            if rescue_three_bead_candidates_payload
            else []
        ),
        {
            "topic": "lbdhodh_stage6_tuning",
            "value": _text(lbdhodh_exploratory_retry_lane_payload.get("lane_label"), "not_ready"),
            "details": (
                f"recommended {_safe_float(lbdhodh_stage6_tuning_surface_payload.get('recommended_observed_threshold_A'), 0.0):.2f}A | "
                f"selected {_text(lbdhodh_exploratory_retry_lane_payload.get('selected_command_kind')) or '-'} | "
                f"next {_text(lbdhodh_exploratory_retry_lane_payload.get('shard_id')) or '-'}"
            ),
        },
        {
            "topic": "lbdhodh_gate51_validation",
            "value": "gate51_validated" if lbdhodh_gate51_validated else "not_validated",
            "details": (
                f"decision {_text(lbdhodh_gate51_validation_review_surface_payload.get('decision')) or '-'} | "
                f"validated {_safe_int(lbdhodh_gate51_validation_review_surface_payload.get('gate51_validation_success_count'), 0)}/"
                f"{_safe_int(lbdhodh_gate51_validation_review_surface_payload.get('gate51_validation_row_count'), 0)} | "
                f"threshold {_safe_float(lbdhodh_gate51_validation_review_surface_payload.get('validated_threshold_A'), 0.0):.2f}A | "
                f"command {_text(lbdhodh_gate51_validation_review_surface_payload.get('validated_command_kind')) or '-'}"
            ),
        },
    ]

    structured = {
        "precision_monitor_artifact": "runs/wetlab_broad_screen_precision_monitor_current.md",
        "primary_failure_surface_artifact": "runs/wetlab_primary_stage6_failure_surface_current.md",
        "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
        "antitarget_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
        "antitarget_progress_artifact": "runs/wetlab_broad_screen_antitarget_progress_current.md",
        "tcruzi_krs1_branch_review_surface_artifact": "runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
        "dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
        "dengue_stage6_tuning_surface_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_current.md",
        "dengue_exploratory_retry_lane_artifact": "runs/wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_current.md",
        "lbdhodh_stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
        "lbdhodh_exploratory_retry_lane_artifact": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
        "lbdhodh_gate51_validation_review_surface_artifact": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
        "kinase_retry_policy_templates_artifact": "runs/wetlab_kinase_retry_policy_templates_current.md",
        "target_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
        "stage6_retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
        "mapping_fix_retry_policy_templates_artifact": "runs/wetlab_mapping_fix_retry_policy_templates_current.md",
        "hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
        "rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
        "rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
        "tcruzi_pde_rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
        "tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
        "tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
    }

    summary = {
        "status": "wetlab_monitor_semantics_ready",
        "resolved_shards": resolved_shards,
        "successful_resolved_shards": successful_resolved_shards,
        "held_resolved_shards": held_resolved_shards,
        "successful_share_pct": successful_share_pct,
        "held_share_pct": held_share_pct,
        "resolved_share_success_pct": successful_share_pct,
        "resolved_share_held_pct": held_share_pct,
        "primary_success_rate_shards_per_hour": primary_success_rate,
        "primary_recent_success_rate_shards_per_hour": rates["primary_recent_success_rate_shards_per_hour"],
        "primary_hold_rate_shards_per_hour": primary_hold_rate,
        "counter_success_rate_shards_per_hour": counter_success_rate,
        "counter_hold_rate_shards_per_hour": counter_hold_rate,
        "counter_success_runtime_median_minutes": counter_rates["success_runtime_median_minutes"],
        "counter_recent_success_runtime_median_minutes": counter_rates["recent_success_runtime_median_minutes"],
        "counter_hold_runtime_median_minutes": counter_rates["hold_runtime_median_minutes"],
        "counter_success_runtime_samples": counter_rates["success_runtime_samples"],
        "counter_hold_runtime_samples": counter_rates["hold_runtime_samples"],
        "primary_success_runtime_median_minutes": _safe_float(monitor_summary.get("median_completed_shard_minutes", 0.0), 0.0),
        "primary_recent_success_runtime_median_minutes": _safe_float(monitor_summary.get("recent_median_completed_shard_minutes", 0.0), 0.0),
        "primary_success_runtime_recent_median_minutes": _safe_float(monitor_summary.get("recent_median_completed_shard_minutes", 0.0), 0.0),
        "primary_hold_runtime_median_minutes": _safe_float(rates["primary_hold_runtime_median_minutes"], 0.0),
        "primary_focus_target_id": primary_focus,
        "primary_focus_shard_id": primary_focus_shard,
        "primary_focus_queue_status": primary_focus_status,
        "retry_focus_target_id": primary_focus if manual_retry_ready else "",
        "retry_focus_shard_id": primary_focus_shard if manual_retry_ready else "",
        "dengue_stage6_tuning_ready": bool(_text(dengue_stage6_summary_payload.get("status")) == "wetlab_dengue_ns2b_ns3_protease_stage6_tuning_surface_ready"),
        "dengue_stage6_recommended_threshold_A": _safe_float(dengue_stage6_summary_payload.get("recommended_threshold_A"), 0.0),
        "dengue_stage6_immediately_runnable_command_kind": _text(dengue_stage6_summary_payload.get("immediately_runnable_command_kind")),
        "dengue_stage6_retry_lane_ready": bool(_text(dengue_stage6_summary_payload.get("status")) == "wetlab_dengue_ns2b_ns3_protease_exploratory_retry_lane_ready"),
        "dengue_stage6_retry_ready_for_manual_retry": bool(dengue_stage6_summary_payload.get("ready_for_manual_retry", False)),
        "dengue_stage6_retry_target_id": _text(dengue_stage6_summary_payload.get("target_id")),
        "dengue_stage6_retry_shard_id": _text(dengue_stage6_summary_payload.get("shard_id")),
        "dengue_stage6_retry_selected_command_kind": _text(dengue_stage6_summary_payload.get("selected_command_kind")),
        "dengue_stage6_retry_lane_label": _text(dengue_stage6_summary_payload.get("lane_label")),
        "dengue_stage6_retry_next_required_step": _text(dengue_stage6_summary_payload.get("next_required_step")),
        "dengue_stage6_source_priority": _text(dengue_stage6_summary_payload.get("source_priority")),
        "lbdhodh_stage6_tuning_ready": bool(_text(lbdhodh_stage6_tuning_surface_payload.get("status")) == "wetlab_lbdhodh_stage6_tuning_surface_ready"),
        "lbdhodh_stage6_recommended_threshold_A": _safe_float(lbdhodh_stage6_tuning_surface_payload.get("recommended_observed_threshold_A"), 0.0),
        "lbdhodh_retry_target_id": _text(lbdhodh_exploratory_retry_lane_payload.get("target_id")),
        "lbdhodh_retry_shard_id": _text(lbdhodh_exploratory_retry_lane_payload.get("shard_id")),
        "lbdhodh_retry_selected_command_kind": _text(lbdhodh_exploratory_retry_lane_payload.get("selected_command_kind")),
        "lbdhodh_retry_lane_label": _text(lbdhodh_exploratory_retry_lane_payload.get("lane_label")),
        "lbdhodh_gate51_validation_review_surface_ready": _text(lbdhodh_gate51_validation_review_surface_payload.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready",
        "lbdhodh_gate51_validated": lbdhodh_gate51_validated,
        "lbdhodh_gate51_validation_decision": _text(lbdhodh_gate51_validation_review_surface_payload.get("decision")),
        "lbdhodh_gate51_validation_validated_command_kind": _text(lbdhodh_gate51_validation_review_surface_payload.get("validated_command_kind")),
        "lbdhodh_gate51_validation_validated_threshold_A": _safe_float(lbdhodh_gate51_validation_review_surface_payload.get("validated_threshold_A"), 0.0),
        "selected_validated_target_id": _text(retry_handoff_summary_payload.get("selected_validated_target_id"), lbdhodh_gate51_validation_review_surface_payload.get("target_id") if lbdhodh_gate51_validated else ""),
        "selected_validated_surface_label": _text(retry_handoff_summary_payload.get("selected_validated_surface_label"), "gate5.1_validation_review" if lbdhodh_gate51_validated else ""),
        "selected_validated_selected_command_kind": _text(retry_handoff_summary_payload.get("selected_validated_selected_command_kind"), lbdhodh_gate51_validation_review_surface_payload.get("validated_command_kind")),
        "selected_validated_threshold_A": _safe_float(retry_handoff_summary_payload.get("selected_validated_threshold_A"), _safe_float(lbdhodh_gate51_validation_review_surface_payload.get("validated_threshold_A"), 0.0)),
        "selected_validated_next_required_step": _text(retry_handoff_summary_payload.get("selected_validated_next_required_step"), lbdhodh_validation_next_step),
        "selected_krs1_branch_review_target_id": _text(retry_handoff_summary_payload.get("selected_krs1_branch_review_target_id")),
        "selected_krs1_branch_review_branch_label": _text(retry_handoff_summary_payload.get("selected_krs1_branch_review_branch_label")),
        "selected_krs1_branch_review_branch_state": _text(retry_handoff_summary_payload.get("selected_krs1_branch_review_branch_state")),
        "selected_krs1_branch_review_selected_command_kind": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_selected_command_kind")
        ),
        "selected_krs1_branch_review_selected_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_selected_threshold_A"), 0.0
        ),
        "selected_krs1_branch_review_next_required_step": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_next_required_step")
        ),
        "tcruzi_pde_rescue_review_surface_ready": _text(tcruzi_pde_rescue_review_surface_payload.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready",
        "tcruzi_pde_rescue_review_target_id": _text(tcruzi_pde_rescue_review_surface_payload.get("target_id")),
        "tcruzi_pde_rescue_review_decision": _text(tcruzi_pde_rescue_review_surface_payload.get("decision")),
        "tcruzi_pde_rescue_review_default_lane_reopen_allowed": bool(tcruzi_pde_rescue_review_surface_payload.get("default_lane_reopen_allowed", False)),
        "tcruzi_pde_rescue_review_branch_to_rescue_only": bool(tcruzi_pde_rescue_review_surface_payload.get("branch_to_rescue_only", False)),
        "tcruzi_pde_rescue_review_promoted_candidate_count": _safe_int(tcruzi_pde_rescue_review_surface_payload.get("promoted_candidate_count"), 0),
        "tcruzi_pde_rescue_review_under_2p5_candidate_count": _safe_int(tcruzi_pde_rescue_review_surface_payload.get("under_2p5_candidate_count"), 0),
        "tcruzi_pde_rescue_review_near_candidate_count": _safe_int(tcruzi_pde_rescue_review_surface_payload.get("near_candidate_count"), 0),
        "tcruzi_pde_rescue_review_selected_command_kind": _text(tcruzi_pde_rescue_review_surface_payload.get("selected_command_kind")),
        "tcruzi_pde_rescue_review_selected_threshold_A": _safe_float(tcruzi_pde_rescue_review_surface_payload.get("selected_threshold_A"), 0.0),
        "tcruzi_pde_promoted_top4_review_packet_ready": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
        "tcruzi_pde_promoted_top4_review_packet_ready_for_operator_review": tcruzi_pde_promoted_top4_gate["packet_ready_for_operator_review"],
        "tcruzi_pde_promoted_top4_review_packet_ready_source": tcruzi_pde_promoted_top4_gate["packet_ready_for_operator_review_source"],
        "tcruzi_pde_promoted_top4_review_packet_wetlab_gate_pass": tcruzi_pde_promoted_top4_gate["wetlab_gate_pass"],
        "tcruzi_pde_promoted_top4_review_packet_wetlab_gate_source": tcruzi_pde_promoted_top4_gate["wetlab_gate_source"],
        "tcruzi_pde_promoted_top4_review_packet_final_gate_pass": tcruzi_pde_promoted_top4_gate["wetlab_final_gate_pass"],
        "tcruzi_pde_promoted_top4_review_packet_final_gate_source": tcruzi_pde_promoted_top4_gate["wetlab_final_gate_source"],
        "tcruzi_pde_promoted_top4_review_packet_claim_gate_available": tcruzi_pde_promoted_top4_gate["claim_gate_available"],
        "tcruzi_pde_promoted_top4_review_packet_claim_gate_source": tcruzi_pde_promoted_top4_gate["claim_gate_source"],
        "tcruzi_pde_promoted_top4_review_packet_claim_ready_for_allatom": tcruzi_pde_promoted_top4_gate["claim_ready_for_allatom"],
        "tcruzi_pde_promoted_top4_review_packet_claim_ready_source": tcruzi_pde_promoted_top4_gate["claim_ready_source"],
        "tcruzi_pde_promoted_top4_review_packet_target_id": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("target_id")),
        "tcruzi_pde_promoted_top4_review_packet_shard_id": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("shard_id")),
        "tcruzi_pde_promoted_top4_review_packet_scope": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("packet_scope")),
        "tcruzi_pde_promoted_top4_review_packet_selected_command_kind": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("selected_command_kind")),
        "tcruzi_pde_promoted_top4_review_packet_strict_threshold_A": _safe_float(tcruzi_pde_promoted_top4_review_packet_payload.get("strict_threshold_A"), 0.0),
        "tcruzi_pde_promoted_top4_review_packet_near_threshold_A": _safe_float(tcruzi_pde_promoted_top4_review_packet_payload.get("near_threshold_A"), 0.0),
        "tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count": _safe_int(tcruzi_pde_promoted_top4_review_packet_payload.get("promoted_candidate_count"), 0),
        "tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count": _safe_int(tcruzi_pde_promoted_top4_review_packet_payload.get("under_2p5_candidate_count"), 0),
        "tcruzi_pde_promoted_top4_review_packet_near_candidate_count": _safe_int(tcruzi_pde_promoted_top4_review_packet_payload.get("near_candidate_count"), 0),
        "tcruzi_pde_promoted_top4_review_packet_best_ligand_id": _text(tcruzi_pde_promoted_top4_review_packet_payload.get("best_ligand_id")),
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name": _text(
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_ligand_id"),
        ),
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable": _text(
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable")
        ),
        "tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution": _text(
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_resolution"), default="unresolved"
        ),
        "tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A": _safe_float(tcruzi_pde_promoted_top4_review_packet_payload.get("best_mean_min_distance_A"), 0.0),
        "tcruzi_pde_rescue_only_branch_summary_ready": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
        "tcruzi_pde_rescue_only_branch_ready_for_operator_review": tcruzi_pde_rescue_branch_gate["packet_ready_for_operator_review"],
        "tcruzi_pde_rescue_only_branch_ready_source": tcruzi_pde_rescue_branch_gate["packet_ready_for_operator_review_source"],
        "tcruzi_pde_rescue_only_branch_wetlab_gate_pass": tcruzi_pde_rescue_branch_gate["wetlab_gate_pass"],
        "tcruzi_pde_rescue_only_branch_wetlab_gate_source": tcruzi_pde_rescue_branch_gate["wetlab_gate_source"],
        "tcruzi_pde_rescue_only_branch_final_gate_pass": tcruzi_pde_rescue_branch_gate["wetlab_final_gate_pass"],
        "tcruzi_pde_rescue_only_branch_final_gate_source": tcruzi_pde_rescue_branch_gate["wetlab_final_gate_source"],
        "tcruzi_pde_rescue_only_branch_claim_gate_available": tcruzi_pde_rescue_branch_gate["claim_gate_available"],
        "tcruzi_pde_rescue_only_branch_claim_gate_source": tcruzi_pde_rescue_branch_gate["claim_gate_source"],
        "tcruzi_pde_rescue_only_branch_claim_ready_for_allatom": tcruzi_pde_rescue_branch_gate["claim_ready_for_allatom"],
        "tcruzi_pde_rescue_only_branch_claim_ready_source": tcruzi_pde_rescue_branch_gate["claim_ready_source"],
        "tcruzi_pde_rescue_only_branch_target_id": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("target_id")),
        "tcruzi_pde_rescue_only_branch_shard_id": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("shard_id")),
        "tcruzi_pde_rescue_only_branch_label": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("branch_label")),
        "tcruzi_pde_rescue_only_branch_state": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("branch_state")),
        "tcruzi_pde_rescue_only_branch_default_lane_reopen_allowed": bool(tcruzi_pde_rescue_only_branch_summary_payload.get("default_lane_reopen_allowed", False)),
        "tcruzi_pde_rescue_only_branch_branch_to_rescue_only": bool(tcruzi_pde_rescue_only_branch_summary_payload.get("branch_to_rescue_only", False)),
        "tcruzi_pde_rescue_only_branch_selected_command_kind": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("selected_command_kind")),
        "tcruzi_pde_rescue_only_branch_selected_threshold_A": _safe_float(tcruzi_pde_rescue_only_branch_summary_payload.get("selected_threshold_A"), 0.0),
        "tcruzi_pde_rescue_only_branch_promoted_top4_packet_ready": bool(tcruzi_pde_rescue_only_branch_summary_payload.get("promoted_top4_packet_ready", False)),
        "tcruzi_pde_rescue_only_branch_promoted_candidate_count": _safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get("promoted_candidate_count"), 0),
        "tcruzi_pde_rescue_only_branch_under_2p5_candidate_count": _safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get("under_2p5_candidate_count"), 0),
        "tcruzi_pde_rescue_only_branch_near_candidate_count": _safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get("near_candidate_count"), 0),
        "tcruzi_pde_rescue_only_branch_best_ligand_id": _text(tcruzi_pde_rescue_only_branch_summary_payload.get("best_ligand_id")),
        "tcruzi_pde_rescue_only_branch_best_compound_name": _text(
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_ligand_id"),
        ),
        "tcruzi_pde_rescue_only_branch_best_compound_name_human_readable": _text(
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_human_readable")
        ),
        "tcruzi_pde_rescue_only_branch_best_compound_name_resolution": _text(
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_resolution"), default="unresolved"
        ),
        "tcruzi_pde_rescue_only_branch_best_mean_min_distance_A": _safe_float(tcruzi_pde_rescue_only_branch_summary_payload.get("best_mean_min_distance_A"), 0.0),
        "selected_rescue_review_best_compound_name": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_best_compound_name"),
            tcruzi_pde_rescue_review_surface_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_rescue_review_surface_payload.get("best_compound_name"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_ligand_id"),
        ),
        "selected_rescue_review_best_compound_name_human_readable": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_best_compound_name_human_readable"),
            tcruzi_pde_rescue_review_surface_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
        ),
        "selected_rescue_review_best_compound_name_resolution": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_best_compound_name_resolution"),
            tcruzi_pde_rescue_review_surface_payload.get("best_compound_name_resolution"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_resolution"),
            default="unresolved",
        ),
        "selected_rescue_review_target_id": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_target_id"),
            tcruzi_pde_rescue_review_surface_payload.get("target_id"),
        ),
        "selected_rescue_review_surface_label": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_surface_label"),
            "pde_rescue_review" if _text(tcruzi_pde_rescue_review_surface_payload.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready" else "",
        ),
        "selected_rescue_review_selected_command_kind": _text(
            retry_handoff_summary_payload.get("selected_rescue_review_selected_command_kind"),
            tcruzi_pde_rescue_review_surface_payload.get("selected_command_kind"),
        ),
        "selected_rescue_review_strict_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_rescue_review_strict_threshold_A"),
            _safe_float(tcruzi_pde_rescue_review_surface_payload.get("strict_threshold_A"), 0.0),
        ),
        "selected_rescue_review_near_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_rescue_review_near_threshold_A"),
            _safe_float(tcruzi_pde_rescue_review_surface_payload.get("near_threshold_A"), 0.0),
        ),
        "selected_rescue_review_promoted_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_rescue_review_promoted_candidate_count"),
            _safe_int(tcruzi_pde_rescue_review_surface_payload.get("promoted_candidate_count"), 0),
        ),
        "selected_rescue_review_under_2p5_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_rescue_review_under_2p5_candidate_count"),
            _safe_int(tcruzi_pde_rescue_review_surface_payload.get("under_2p5_candidate_count"), 0),
        ),
        "selected_rescue_review_next_required_step": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_next_required_step"),
            retry_handoff_summary_payload.get("selected_rescue_review_next_required_step"),
            tcruzi_pde_rescue_branch_next_step,
            tcruzi_pde_rescue_review_next_step,
        ),
        "selected_rescue_branch_target_id": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_target_id"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("target_id"),
        ),
        "selected_rescue_branch_surface_label": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_surface_label"),
            "pde_rescue_only_branch" if _text(tcruzi_pde_rescue_only_branch_summary_payload.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready" else "",
        ),
        "selected_rescue_branch_selected_command_kind": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_selected_command_kind"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("selected_command_kind"),
        ),
        "selected_rescue_branch_best_compound_name": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_best_compound_name"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_ligand_id"),
        ),
        "selected_rescue_branch_best_compound_name_human_readable": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_best_compound_name_human_readable"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_human_readable"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_human_readable"),
        ),
        "selected_rescue_branch_best_compound_name_resolution": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_best_compound_name_resolution"),
            tcruzi_pde_rescue_only_branch_summary_payload.get("best_compound_name_resolution"),
            tcruzi_pde_promoted_top4_review_packet_payload.get("best_compound_name_resolution"),
            default="unresolved",
        ),
        "selected_rescue_branch_selected_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_rescue_branch_selected_threshold_A"),
            _safe_float(tcruzi_pde_rescue_only_branch_summary_payload.get("selected_threshold_A"), 0.0),
        ),
        "selected_rescue_branch_promoted_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_rescue_branch_promoted_candidate_count"),
            _safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get("promoted_candidate_count"), 0),
        ),
        "selected_rescue_branch_under_2p5_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_rescue_branch_under_2p5_candidate_count"),
            _safe_int(tcruzi_pde_rescue_only_branch_summary_payload.get("under_2p5_candidate_count"), 0),
        ),
        "selected_rescue_branch_operator_packet_ready": selected_rescue_operator_gate["packet_ready_for_operator_review"],
        "selected_rescue_branch_operator_packet_ready_for_operator_review": selected_rescue_operator_gate["packet_ready_for_operator_review"],
        "selected_rescue_branch_operator_packet_ready_source": selected_rescue_operator_gate["packet_ready_for_operator_review_source"],
        "selected_rescue_branch_operator_packet_wetlab_gate_pass": selected_rescue_operator_gate["wetlab_gate_pass"],
        "selected_rescue_branch_operator_packet_wetlab_gate_source": selected_rescue_operator_gate["wetlab_gate_source"],
        "selected_rescue_branch_operator_packet_final_gate_pass": selected_rescue_operator_gate["wetlab_final_gate_pass"],
        "selected_rescue_branch_operator_packet_final_gate_source": selected_rescue_operator_gate["wetlab_final_gate_source"],
        "selected_rescue_branch_operator_packet_claim_gate_available": selected_rescue_operator_gate["claim_gate_available"],
        "selected_rescue_branch_operator_packet_claim_gate_source": selected_rescue_operator_gate["claim_gate_source"],
        "selected_rescue_branch_operator_packet_claim_ready_for_allatom": selected_rescue_operator_gate["claim_ready_for_allatom"],
        "selected_rescue_branch_operator_packet_claim_ready_source": selected_rescue_operator_gate["claim_ready_source"],
        "selected_rescue_branch_operator_packet_scope": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_operator_packet_scope")
        ),
        "rescue_only_branch_templates_ready": bool(
            retry_handoff_summary_payload.get("rescue_only_branch_templates_ready", False)
        ),
        "rescue_only_branch_template_target_count": _safe_int(
            retry_handoff_summary_payload.get("rescue_only_branch_template_target_count")
        ),
        "rescue_only_branch_focus_target_id": _text(
            retry_handoff_summary_payload.get("rescue_only_branch_focus_target_id")
        ),
        "rescue_only_branch_focus_template_label": _text(
            retry_handoff_summary_payload.get("rescue_only_branch_focus_template_label")
        ),
        "rescue_only_branch_focus_surface_label": _text(
            retry_handoff_summary_payload.get("rescue_only_branch_focus_surface_label")
        ),
        "rescue_only_branch_focus_selected_command_kind": _text(
            retry_handoff_summary_payload.get("rescue_only_branch_focus_selected_command_kind")
        ),
        "rescue_only_branch_focus_selected_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("rescue_only_branch_focus_selected_threshold_A")
        ),
        "selected_rescue_branch_next_required_step": _text(
            retry_handoff_summary_payload.get("selected_rescue_branch_next_required_step"),
            tcruzi_pde_rescue_branch_next_step,
        ),
        "allatom_family_ready": bool(retry_handoff_summary_payload.get("allatom_family_ready", False)),
        "allatom_family_target_count": _safe_int(
            retry_handoff_summary_payload.get("allatom_family_target_count"),
            0,
        ),
        "allatom_family_surface_count": _safe_int(
            retry_handoff_summary_payload.get("allatom_family_surface_count"),
            0,
        ),
        "allatom_family_focus_target_id": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_target_id")
        ),
        "allatom_family_focus_surface_label": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_surface_label")
        ),
        "allatom_family_focus_commercial_reported_v1": bool(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_reported_v1", False)
        ),
        "allatom_family_focus_commercial_schema_version": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_schema_version")
        ),
        "allatom_family_focus_commercial_hard_gate_pass_v1": bool(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_hard_gate_pass_v1", False)
        ),
        "allatom_family_focus_commercial_overall_score_v1": _safe_float(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_overall_score_v1"),
            0.0,
        ),
        "allatom_family_focus_commercial_risk_bucket_v1": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_risk_bucket_v1")
        ),
        "allatom_family_focus_commercial_decision_class_v1": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_decision_class_v1")
        ),
        "allatom_family_focus_commercial_primary_upgrade_actions_v1": list(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_primary_upgrade_actions_v1", [])
            or []
        ),
        "allatom_family_focus_commercial_primary_upgrade_actions_text_v1": _text(
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_primary_upgrade_actions_text_v1")
        ),
        "selected_allatom_target_id": _text(
            retry_handoff_summary_payload.get("selected_allatom_target_id")
        ),
        "selected_allatom_surface_label": _text(
            retry_handoff_summary_payload.get("selected_allatom_surface_label")
        ),
        "selected_allatom_selected_command_kind": _text(
            retry_handoff_summary_payload.get("selected_allatom_selected_command_kind")
        ),
        "selected_allatom_selected_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_allatom_selected_threshold_A"),
            0.0,
        ),
        "selected_allatom_packet_scope": _text(
            retry_handoff_summary_payload.get("selected_allatom_packet_scope")
        ),
        "selected_allatom_packet_ready_for_operator_review": selected_allatom_gate["packet_ready_for_operator_review"],
        "selected_allatom_operator_review_ready": selected_allatom_gate["packet_ready_for_operator_review"],
        "selected_allatom_packet_ready_for_operator_review_source": selected_allatom_operator_ready_source,
        "selected_allatom_operator_review_ready_source": selected_allatom_operator_ready_source,
        "selected_allatom_wetlab_gate_pass": selected_allatom_gate["wetlab_gate_pass"],
        "selected_allatom_wetlab_gate_source": selected_allatom_wetlab_gate_source,
        "selected_allatom_wetlab_final_gate_pass": selected_allatom_gate["wetlab_final_gate_pass"],
        "selected_allatom_wetlab_final_gate_source": selected_allatom_final_gate_source,
        "selected_allatom_claim_gate_available": selected_allatom_gate["claim_gate_available"],
        "selected_allatom_claim_gate_source": selected_allatom_claim_gate_source,
        "selected_allatom_claim_ready_for_allatom": selected_allatom_gate["claim_ready_for_allatom"],
        "selected_allatom_claim_ready_source": selected_allatom_claim_ready_source,
        "selected_allatom_gate_source_surface_label": selected_allatom_gate_source_surface_label,
        "selected_allatom_readiness_semantics": selected_allatom_readiness_semantics,
        "selected_allatom_human_summary": _joined(
            selected_allatom_actionability_human_summary or selected_allatom_actionability_brief_summary,
            f"Actionability: {selected_allatom_actionability_display}" if selected_allatom_actionability_display else "",
        ),
        "selected_allatom_actionability_status": selected_allatom_actionability_status,
        "selected_allatom_actionability_brief_summary": selected_allatom_actionability_brief_summary,
        "selected_allatom_actionability_human_summary": selected_allatom_actionability_human_summary,
        "selected_allatom_actionability_block_reason": selected_allatom_actionability_block_reason,
        "selected_allatom_actionability_block_reason_codes": list(
            selected_allatom_actionability.get("block_reason_codes", []) or []
        ),
        "selected_allatom_actionability_soft_guidance_reasons": list(
            selected_allatom_actionability.get("soft_guidance_reasons", []) or []
        ),
        "selected_allatom_actionability_required_calculations": list(
            selected_allatom_actionability.get("required_calculations", []) or []
        ),
        "selected_allatom_actionability_required_calculations_text": selected_allatom_actionability_required_calculations_text,
        "selected_allatom_actionability_action_list": list(
            selected_allatom_actionability.get("action_list", []) or []
        ),
        "selected_allatom_actionability_action_list_text": selected_allatom_actionability_action_list_text,
        "selected_allatom_actionability_claim_requirement_mode": selected_allatom_actionability_claim_requirement_mode,
        "selected_allatom_actionability_claim_requirement_status": selected_allatom_actionability_claim_requirement_status,
        "selected_allatom_actionability_claim_requirement_reason": selected_allatom_actionability_claim_requirement_reason,
        "selected_allatom_actionability_next_expensive_lane": selected_allatom_actionability_next_expensive_lane,
        "selected_allatom_actionability_next_expensive_lane_reason": selected_allatom_actionability_next_expensive_lane_reason,
        "selected_allatom_actionability_translation_gate_v2_failed_metrics": list(
            selected_allatom_translation_gate_v2_failed_metrics
        ),
        "selected_allatom_actionability_translation_gate_v2_missing_metrics": list(
            selected_allatom_translation_gate_v2_missing_metrics
        ),
        "selected_allatom_actionability_translation_gate_v2_thresholds": dict(
            selected_allatom_translation_gate_v2_thresholds
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
        "selected_allatom_claim_gate_source": selected_allatom_claim_gate_source,
        "selected_allatom_claim_gate_policy_version": selected_allatom_claim_gate_policy_version,
        "selected_allatom_claim_pass_core_gate": selected_allatom_focus_summary.get(
            "selected_allatom_claim_pass_core_gate",
            selected_allatom_focus_summary.get("pass_core_gate", selected_allatom_claim_pass_core_gate),
        ),
        "selected_allatom_claim_core_failed_metrics": list(
            _normalize_string_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_core_failed_metrics",
                    selected_allatom_focus_summary.get("core_failed_metrics"),
                )
            )
            or selected_allatom_claim_core_failed_metrics
        ),
        "selected_allatom_claim_core_missing_metrics": list(
            _normalize_string_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_core_missing_metrics",
                    selected_allatom_focus_summary.get("core_missing_metrics"),
                )
            )
            or selected_allatom_claim_core_missing_metrics
        ),
        "selected_allatom_claim_failed_metrics": list(
            _normalize_string_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_failed_metrics",
                    selected_allatom_focus_summary.get("claim_failed_metrics"),
                )
            )
            or selected_allatom_claim_failed_metrics
        ),
        "selected_allatom_claim_missing_metrics": list(
            _normalize_string_list(
                selected_allatom_focus_summary.get(
                    "selected_allatom_claim_missing_metrics",
                    selected_allatom_focus_summary.get("claim_missing_metrics"),
                )
            )
            or selected_allatom_claim_missing_metrics
        ),
        "selected_allatom_claim_requirement_mode": _text(
            selected_allatom_canonical.get("raw_claim_requirement_mode"),
            selected_allatom_focus_summary.get("selected_allatom_claim_requirement_mode"),
            selected_allatom_focus_summary.get("claim_gate_requirement_mode"),
        ),
        "selected_allatom_claim_requirement_provenance": _text(
            selected_allatom_canonical.get("raw_claim_requirement_provenance"),
            selected_allatom_focus_summary.get("selected_allatom_claim_requirement_provenance"),
            selected_allatom_focus_summary.get("claim_gate_requirement_provenance"),
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
            selected_allatom_focus_summary.get("selected_allatom_claim_requirement_reason"),
            selected_allatom_focus_summary.get("claim_gate_requirement_reason"),
        ),
        "selected_allatom_claim_requirement_actions": list(
            dict(selected_allatom_raw_claim or {}).get(
                "requirement_actions",
                _normalize_string_list(
                    selected_allatom_focus_summary.get(
                        "selected_allatom_claim_requirement_actions",
                        selected_allatom_focus_summary.get(
                            "claim_gate_requirement_actions"
                        ),
                    )
                ),
            )
            or []
        ),
        "selected_allatom_commercial_reported_v1": selected_allatom_commercial_reported,
        "selected_allatom_commercial_schema_version": _text(
            retry_handoff_summary_payload.get("selected_allatom_commercial_schema_version"),
            retry_handoff_summary_payload.get("allatom_family_focus_commercial_schema_version"),
            selected_allatom_focus_summary.get("commercial_schema_version"),
            selected_allatom_focus_summary.get("commercial_schema_version_v1"),
        ),
        "selected_allatom_commercial_hard_gate_pass_v1": selected_allatom_commercial_hard_gate_pass,
        "selected_allatom_commercial_overall_score_v1": selected_allatom_commercial_overall_score,
        "selected_allatom_commercial_risk_bucket_v1": selected_allatom_commercial_risk_bucket,
        "selected_allatom_commercial_decision_class_v1": selected_allatom_commercial_decision_class,
        "selected_allatom_commercial_primary_upgrade_actions_v1": list(selected_allatom_commercial_actions),
        "selected_allatom_commercial_primary_upgrade_actions_text_v1": selected_allatom_commercial_actions_text,
        "selected_allatom_commercial_source_surface_label_v1": selected_allatom_commercial_source_surface_label,
        "selected_allatom_commercial_reported_v2": selected_allatom_commercial_reported_v2,
        "selected_allatom_commercial_schema_version_v2": selected_allatom_commercial_schema_version_v2,
        "selected_allatom_commercial_hard_gate_pass_v2": selected_allatom_commercial_hard_gate_pass_v2,
        "selected_allatom_commercial_soft_score_v2": selected_allatom_commercial_soft_score_v2,
        "selected_allatom_commercial_confidence_score_v2": selected_allatom_commercial_confidence_score_v2,
        "selected_allatom_commercial_overall_score_v2": selected_allatom_commercial_overall_score_v2,
        "selected_allatom_commercial_risk_bucket_v2": selected_allatom_commercial_risk_bucket_v2,
        "selected_allatom_commercial_decision_class_v2": selected_allatom_commercial_decision_class_v2,
        "selected_allatom_commercial_primary_upgrade_actions_v2": list(selected_allatom_commercial_actions_v2),
        "selected_allatom_commercial_primary_upgrade_actions_text_v2": selected_allatom_commercial_actions_text_v2,
        "selected_allatom_commercial_human_summary_v2": selected_allatom_commercial_human_summary_v2,
        "selected_allatom_translation_gate_status": selected_allatom_translation_gate_status,
        "selected_allatom_translation_gate_score": selected_allatom_translation_gate_score,
        "selected_allatom_translation_gate_reason": selected_allatom_translation_gate_reason,
        "selected_allatom_focus_shortlist_tier": selected_allatom_focus_shortlist_tier,
        "selected_allatom_recommended_next_expensive_lane": selected_allatom_recommended_next_expensive_lane,
        "selected_allatom_recommended_next_expensive_lane_reason": selected_allatom_recommended_next_expensive_lane_reason,
        "selected_allatom_translation_human_summary": selected_allatom_translation_human_summary,
        "selected_allatom_best_compound_name": _text(
            retry_handoff_summary_payload.get("selected_allatom_best_compound_name")
        ),
        "selected_allatom_best_compound_name_human_readable": _text(
            retry_handoff_summary_payload.get("selected_allatom_best_compound_name_human_readable")
        ),
        "selected_allatom_best_compound_name_resolution": _text(
            retry_handoff_summary_payload.get("selected_allatom_best_compound_name_resolution"),
            default="unresolved",
        ),
        "selected_allatom_best_mean_min_distance_A": _safe_float(
            retry_handoff_summary_payload.get("selected_allatom_best_mean_min_distance_A"),
            0.0,
        ),
        "selected_allatom_promoted_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_allatom_promoted_candidate_count"),
            0,
        ),
        "selected_allatom_under_2p5_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_allatom_under_2p5_candidate_count"),
            0,
        ),
        "selected_allatom_near_candidate_count": _safe_int(
            retry_handoff_summary_payload.get("selected_allatom_near_candidate_count"),
            0,
        ),
        "selected_allatom_next_required_step": _text(
            retry_handoff_summary_payload.get("selected_allatom_next_required_step"),
            selected_allatom_focus_summary.get("next_required_step"),
        ),
        "selected_manual_retry_target_id": _text(
            selected_manual_retry_lane_payload.get("target_id"),
            retry_handoff_summary_payload.get("selected_manual_retry_target_id"),
        ),
        "selected_manual_retry_shard_id": _text(
            _lane_shard_display(selected_manual_retry_lane),
            retry_handoff_summary_payload.get("selected_manual_retry_shard_id"),
        ),
        "selected_manual_retry_selected_command_kind": _text(
            selected_manual_retry_lane_payload.get("selected_command_kind"),
            retry_handoff_summary_payload.get("selected_manual_retry_selected_command_kind"),
        ),
        "selected_manual_retry_lane_label": _text(
            selected_manual_retry_lane_payload.get("followup_lane_label"),
            selected_manual_retry_lane_payload.get("lane_label"),
            retry_handoff_summary_payload.get("selected_manual_retry_lane_label"),
        ),
        "selected_manual_retry_freeze_state": selected_manual_retry_freeze_state,
        "selected_manual_retry_freeze_note": selected_manual_retry_freeze_note,
        "stk17b_exploratory_followup_target_id": _text(stk17b_exploratory_followup_lane_payload.get("target_id")),
        "stk17b_exploratory_followup_shard_id": _lane_shard_display(stk17b_exploratory_followup_lane),
        "stk17b_exploratory_followup_selected_command_kind": _text(stk17b_exploratory_followup_lane_payload.get("selected_command_kind")),
        "stk17b_exploratory_followup_lane_label": _text(
            stk17b_exploratory_followup_lane_payload.get("followup_lane_label"),
            stk17b_exploratory_followup_lane_payload.get("lane_label"),
        ),
        "stk17b_exploratory_followup_freeze_state": _text(
            stk17b_exploratory_followup_lane_payload.get("hard_freeze_state"),
            stk17b_exploratory_followup_lane_payload.get("freeze_state"),
        ),
        "stk17b_exploratory_followup_freeze_note": _text(stk17b_exploratory_followup_lane_payload.get("freeze_note")),
        "stk17b_exploratory_followup_followup_shard_ids": _text(
            stk17b_exploratory_followup_lane_payload.get("followup_shard_ids")
        ),
        "stk17b_followup_lane_label": _text(
            stk17b_exploratory_followup_lane_payload.get("followup_lane_label"),
            stk17b_exploratory_followup_lane_payload.get("lane_label"),
        ),
        "stk17b_followup_freeze_state": _text(
            stk17b_exploratory_followup_lane_payload.get("hard_freeze_state"),
            stk17b_exploratory_followup_lane_payload.get("freeze_state"),
        ),
        "stk17b_followup_freeze_note": _text(stk17b_exploratory_followup_lane_payload.get("freeze_note")),
        "stk17b_followup_followup_shard_ids": _text(stk17b_exploratory_followup_lane_payload.get("followup_shard_ids")),
        "stk17b_followup_review_decision": _text(stk17b_followup_review_summary.get("decision")),
        "stk17b_followup_review_decision_rationale": _text(stk17b_followup_review_summary.get("decision_rationale")),
        "stk17b_followup_review_next_required_step": stk17b_followup_review_next_step,
        "stk17b_exploratory_retry_target_id": _text(stk17b_exploratory_retry_lane_payload.get("target_id")),
        "stk17b_exploratory_retry_shard_id": _text(stk17b_exploratory_retry_lane_payload.get("shard_id")),
        "stk17b_exploratory_retry_selected_command_kind": _text(stk17b_exploratory_retry_lane_payload.get("selected_command_kind")),
        "stk17b_manual_retry_target_id": _text(stk17b_manual_retry_lane_payload.get("target_id")),
        "stk17b_manual_retry_shard_id": _text(stk17b_manual_retry_lane_payload.get("shard_id")),
        "stk17b_manual_retry_selected_command_kind": _text(stk17b_manual_retry_lane_payload.get("selected_command_kind")),
        "kinase_retry_policy_templates_ready": _text(kinase_retry_policy_templates_summary.get("status")) == "wetlab_kinase_retry_policy_templates_ready",
        "kinase_retry_template_target_count": _safe_int(kinase_retry_policy_templates_summary.get("template_target_count"), 0),
        "kinase_retry_empirical_validated_target_count": _safe_int(kinase_retry_policy_templates_summary.get("empirical_validated_target_count"), 0),
        "kinase_retry_gate45_only_target_count": _safe_int(kinase_retry_policy_templates_summary.get("gate45_only_target_count"), 0),
        "kinase_retry_guarded_gate55_candidate_target_count": _safe_int(kinase_retry_policy_templates_summary.get("guarded_gate55_candidate_target_count"), 0),
        "kinase_retry_focus_target_id": _text(kinase_retry_policy_templates_summary.get("focus_target_id")),
        "kinase_retry_focus_template_label": _text(kinase_retry_policy_templates_summary.get("focus_template_label")),
        "kinase_retry_focus_selected_command_kind": _text(kinase_retry_policy_templates_summary.get("focus_selected_command_kind")),
        "kinase_retry_next_required_step": _text(kinase_retry_policy_templates_summary.get("next_required_step")),
        "target_retry_policy_templates_ready": _text(target_retry_policy_templates_summary.get("status")) == "wetlab_target_retry_policy_templates_ready",
        "target_retry_template_target_count": _safe_int(target_retry_policy_templates_summary.get("template_target_count"), 0),
        "target_retry_empirical_validated_target_count": _safe_int(target_retry_policy_templates_summary.get("empirical_validated_target_count"), 0),
        "target_retry_non_kinase_template_target_count": _safe_int(target_retry_policy_templates_summary.get("non_kinase_template_target_count"), 0),
        "target_retry_focus_target_id": _text(target_retry_policy_templates_summary.get("focus_target_id")),
        "target_retry_focus_template_label": _text(target_retry_policy_templates_summary.get("focus_template_label")),
        "target_retry_focus_selected_command_kind": _text(target_retry_policy_templates_summary.get("focus_selected_command_kind")),
        "target_retry_focus_selected_threshold_A": _safe_float(target_retry_policy_templates_summary.get("focus_selected_threshold_A"), 0.0),
        "target_retry_next_required_step": _text(target_retry_policy_templates_summary.get("next_required_step")),
        "stage6_retry_policy_templates_ready": _text(stage6_retry_policy_templates_summary.get("status")) == "wetlab_target_retry_policy_templates_ready",
        "stage6_retry_template_target_count": _safe_int(stage6_retry_policy_templates_summary.get("template_target_count"), 0),
        "stage6_retry_gate45_candidate_target_count": _safe_int(stage6_retry_policy_templates_summary.get("gate45_candidate_target_count"), 0),
        "stage6_retry_gate51_candidate_target_count": _safe_int(stage6_retry_policy_templates_summary.get("gate51_candidate_target_count"), 0),
        "stage6_retry_ready_targets": _text(stage6_retry_policy_templates_summary.get("ready_targets")),
        "stage6_retry_gate45_targets": _text(stage6_retry_policy_templates_summary.get("gate45_targets")),
        "stage6_retry_gate51_targets": _text(stage6_retry_policy_templates_summary.get("gate51_targets")),
        "stage6_retry_focus_target_id": _text(stage6_retry_policy_templates_summary.get("focus_target_id")),
        "stage6_retry_focus_template_label": _text(stage6_retry_policy_templates_summary.get("focus_template_label")),
        "stage6_retry_focus_selected_command_kind": _text(stage6_retry_policy_templates_summary.get("focus_selected_command_kind")),
        "stage6_retry_focus_selected_threshold_A": _safe_float(stage6_retry_policy_templates_summary.get("focus_selected_threshold_A"), 0.0),
        "stage6_retry_next_required_step": _text(stage6_retry_policy_templates_summary.get("next_required_step")),
        "krs1_branch_review_ready": krs1_branch_review_ready,
        "krs1_branch_review_target_id": _text(krs1_branch_review_summary_payload.get("target_id")),
        "krs1_branch_review_branch_label": _text(krs1_branch_review_summary_payload.get("branch_label")),
        "krs1_branch_review_branch_state": _text(krs1_branch_review_summary_payload.get("branch_state")),
        "krs1_branch_review_source_priority": _text(krs1_branch_review_summary_payload.get("source_priority")),
        "krs1_branch_review_decision_source_priority": _text(krs1_branch_review_summary_payload.get("decision_source_priority")),
        "krs1_branch_review_stage6_tuning_surface_ready": bool(
            krs1_branch_review_summary_payload.get("stage6_tuning_surface_ready", False)
        ),
        "krs1_branch_review_stage6_tuning_source_priority": _text(
            krs1_branch_review_summary_payload.get("stage6_tuning_source_priority")
        ),
        "krs1_branch_review_stage6_tuning_recommended_threshold_A": _safe_float(
            krs1_branch_review_summary_payload.get("stage6_tuning_recommended_threshold_A"), 0.0
        ),
        "krs1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
            krs1_branch_review_summary_payload.get("stage6_tuning_immediately_runnable_command_kind")
        ),
        "krs1_branch_review_stage6_tuning_next_required_step": _text(
            krs1_branch_review_summary_payload.get("stage6_tuning_next_required_step")
        ),
        "krs1_branch_review_exploratory_retry_lane_ready": bool(
            krs1_branch_review_summary_payload.get("exploratory_retry_lane_ready", False)
        ),
        "krs1_branch_review_exploratory_source_priority": _text(
            krs1_branch_review_summary_payload.get("exploratory_source_priority")
        ),
        "krs1_branch_review_exploratory_retry_lane_label": _text(
            krs1_branch_review_summary_payload.get("exploratory_retry_lane_label")
        ),
        "krs1_branch_review_exploratory_retry_selected_command_kind": _text(
            krs1_branch_review_summary_payload.get("exploratory_retry_selected_command_kind")
        ),
        "krs1_branch_review_exploratory_retry_selected_threshold_A": _safe_float(
            krs1_branch_review_summary_payload.get("exploratory_retry_selected_threshold_A"), 0.0
        ),
        "krs1_branch_review_exploratory_retry_next_required_step": _text(
            krs1_branch_review_summary_payload.get("exploratory_retry_next_required_step")
        ),
        "krs1_branch_review_successor_target": _text(krs1_branch_review_summary_payload.get("successor_target")),
        "krs1_branch_review_successor_gate_state": _text(krs1_branch_review_summary_payload.get("successor_gate_state")),
        "krs1_branch_review_successor_gate_open": bool(krs1_branch_review_summary_payload.get("successor_gate_open", False)),
        "krs1_branch_review_next_required_step": _text(krs1_branch_review_summary_payload.get("next_required_step")),
        "selected_krs1_branch_review_target_id": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_target_id"),
            krs1_branch_review_summary_payload.get("target_id"),
        )
        if selected_krs1_branch_review_next_step
        else "",
        "selected_krs1_branch_review_surface_label": "krs1_branch_review_surface"
        if selected_krs1_branch_review_next_step
        else "",
        "selected_krs1_branch_review_branch_label": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_branch_label"),
            krs1_branch_review_summary_payload.get("branch_label"),
        )
        if selected_krs1_branch_review_next_step
        else "",
        "selected_krs1_branch_review_branch_state": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_branch_state"),
            krs1_branch_review_summary_payload.get("branch_state"),
        )
        if selected_krs1_branch_review_next_step
        else "",
        "selected_krs1_branch_review_selected_command_kind": _text(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_selected_command_kind"),
            krs1_branch_review_summary_payload.get("exploratory_retry_selected_command_kind")
        )
        if selected_krs1_branch_review_next_step
        else "",
        "selected_krs1_branch_review_selected_threshold_A": _safe_float(
            retry_handoff_summary_payload.get("selected_krs1_branch_review_selected_threshold_A"),
            _safe_float(krs1_branch_review_summary_payload.get("exploratory_retry_selected_threshold_A"), 0.0),
        )
        if selected_krs1_branch_review_next_step
        else 0.0,
        "selected_krs1_branch_review_next_required_step": selected_krs1_branch_review_next_step,
        "dpre1_branch_review_ready": dpre1_branch_review_ready,
        "dpre1_branch_review_target_id": _text(dpre1_branch_review_summary_payload.get("target_id")),
        "dpre1_branch_review_branch_label": _text(dpre1_branch_review_summary_payload.get("branch_label")),
        "dpre1_branch_review_branch_state": _text(dpre1_branch_review_summary_payload.get("branch_state")),
        "dpre1_branch_review_source_priority": _text(dpre1_branch_review_summary_payload.get("source_priority")),
        "dpre1_branch_review_result_review_status": _text(dpre1_branch_review_summary_payload.get("result_review_status")),
        "dpre1_branch_review_result_summary_status": _text(dpre1_branch_review_summary_payload.get("result_summary_status")),
        "dpre1_branch_review_launch_packet_status": _text(dpre1_branch_review_summary_payload.get("launch_packet_status")),
        "dpre1_branch_review_stage6_tuning_surface_ready": bool(dpre1_branch_review_summary_payload.get("stage6_tuning_surface_ready", False)),
        "dpre1_branch_review_stage6_tuning_source_priority": _text(dpre1_branch_review_summary_payload.get("stage6_tuning_source_priority")),
        "dpre1_branch_review_stage6_tuning_recommended_threshold_A": _safe_float(
            dpre1_branch_review_summary_payload.get("stage6_tuning_recommended_threshold_A"), 0.0
        ),
        "dpre1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
            dpre1_branch_review_summary_payload.get("stage6_tuning_immediately_runnable_command_kind")
        ),
        "dpre1_branch_review_exploratory_retry_lane_ready": bool(
            dpre1_branch_review_summary_payload.get("exploratory_retry_lane_ready", False)
        ),
        "dpre1_branch_review_exploratory_source_priority": _text(
            dpre1_branch_review_summary_payload.get("exploratory_source_priority")
        ),
        "dpre1_branch_review_exploratory_retry_lane_label": _text(
            dpre1_branch_review_summary_payload.get("exploratory_retry_lane_label")
        ),
        "dpre1_branch_review_exploratory_retry_selected_command_kind": _text(
            dpre1_branch_review_summary_payload.get("exploratory_retry_selected_command_kind")
        ),
        "dpre1_branch_review_exploratory_retry_selected_threshold_A": _safe_float(
            dpre1_branch_review_summary_payload.get("exploratory_retry_selected_threshold_A"), 0.0
        ),
        "dpre1_branch_review_successor_target": _text(dpre1_branch_review_summary_payload.get("successor_target")),
        "dpre1_branch_review_successor_gate_state": _text(dpre1_branch_review_summary_payload.get("successor_gate_state")),
        "dpre1_branch_review_next_required_step": _text(dpre1_branch_review_summary_payload.get("next_required_step")),
        "mapping_fix_retry_policy_templates_ready": _text(mapping_fix_retry_policy_templates_summary.get("status")) == "wetlab_mapping_fix_retry_policy_templates_ready",
        "mapping_fix_retry_template_target_count": _safe_int(mapping_fix_retry_policy_templates_summary.get("template_target_count"), 0),
        "mapping_fix_retry_ready_target_count": _safe_int(mapping_fix_retry_policy_templates_summary.get("ready_target_count"), 0),
        "mapping_fix_retry_ready_targets": _text(mapping_fix_retry_policy_templates_summary.get("ready_targets")),
        "mapping_fix_retry_focus_target_id": _text(mapping_fix_retry_policy_templates_summary.get("focus_target_id")),
        "mapping_fix_retry_focus_template_label": _text(mapping_fix_retry_policy_templates_summary.get("focus_template_label")),
        "mapping_fix_retry_focus_selected_command_kind": _text(mapping_fix_retry_policy_templates_summary.get("focus_selected_command_kind")),
        "mapping_fix_retry_next_required_step": _text(mapping_fix_retry_policy_templates_summary.get("next_required_step")),
        "hard_target_rescue_lane_ready": bool(_text(hard_target_rescue_lane_payload.get("status")) == "wetlab_hard_target_rescue_lane_ready"),
        "hard_target_rescue_lane_target_count": 1 if _text(hard_target_rescue_lane_payload.get("target_id")) else 0,
        "hard_target_rescue_lane_rescue_eligible_target_count": 1 if bool(hard_target_rescue_lane_payload.get("rescue_eligible", False)) else 0,
        "hard_target_rescue_lane_target_id": _text(hard_target_rescue_lane_payload.get("target_id")),
        "hard_target_rescue_lane_shard_id": _text(hard_target_rescue_lane_payload.get("shard_id")),
        "hard_target_rescue_lane_stage1_ok": bool(hard_target_rescue_lane_payload.get("stage1_ok", False)),
        "hard_target_rescue_lane_stage6_fail": bool(hard_target_rescue_lane_payload.get("stage6_fail", False)),
        "hard_target_rescue_lane_auto_hold_streak": _safe_int(hard_target_rescue_lane_payload.get("auto_hold_streak"), 0),
        "hard_target_rescue_lane_selected_command_kind": _text(hard_target_rescue_lane_payload.get("selected_command_kind")),
        "hard_target_rescue_lane_lane_label": _text(hard_target_rescue_lane_payload.get("lane_label")),
        "hard_target_rescue_lane_next_required_step": _text(hard_target_rescue_lane_payload.get("next_required_step")),
        "rescue_anchor_artifacts_ready": bool(_text(rescue_anchor_artifacts_payload.get("status")) == "wetlab_rescue_anchor_artifacts_ready"),
        "rescue_anchor_target_count": 1 if _text(rescue_anchor_artifacts_payload.get("target_id")) else 0,
        "rescue_anchor_target_id": _text(rescue_anchor_artifacts_payload.get("target_id")),
        "rescue_anchor_rescue_only": bool(rescue_anchor_artifacts_payload.get("rescue_only", False)),
        "rescue_anchor_artifact_count": _safe_int(rescue_anchor_artifacts_payload.get("anchor_artifact_count"), 0),
        "rescue_anchor_native_anchor_artifact": _text(rescue_anchor_artifacts_payload.get("native_anchor_artifact")),
        "rescue_anchor_pocket_anchor_artifact": _text(rescue_anchor_artifacts_payload.get("pocket_anchor_artifact")),
        "rescue_anchor_next_required_step": _text(rescue_anchor_artifacts_payload.get("next_required_step")),
        "rescue_three_bead_candidates_ready": bool(_text(rescue_three_bead_candidates_payload.get("status")) == "wetlab_rescue_three_bead_candidates_ready"),
        "rescue_three_bead_candidate_target_count": 1 if _text(rescue_three_bead_candidates_payload.get("target_id")) else 0,
        "rescue_three_bead_candidate_target_id": _text(rescue_three_bead_candidates_payload.get("target_id")),
        "rescue_three_bead_candidate_count": _safe_int(rescue_three_bead_candidates_payload.get("candidate_count"), 0),
        "rescue_three_bead_candidate_top_n": _safe_int(rescue_three_bead_candidates_payload.get("top_n"), 0),
        "rescue_three_bead_candidate_selected_command_kind": _text(rescue_three_bead_candidates_payload.get("selected_command_kind")),
        "rescue_three_bead_candidate_selected_threshold_A": _safe_float(rescue_three_bead_candidates_payload.get("selected_threshold_A"), 0.0),
        "rescue_three_bead_candidate_next_required_step": _text(rescue_three_bead_candidates_payload.get("next_required_step")),
        "retry_manual_step": manual_retry_step if manual_retry_ready else "",
        "counter_primary_target_id": counter_primary,
        "counter_anti_target_id": counter_anti,
        "counter_shard_id": counter_shard,
        "counter_queue_status": counter_status,
        "guard_hold_limit": guard_hold_limit,
        "guard_active": guard_active,
        "guard_blocked_target_id": guard_blocked_target,
        "guard_hold_streak": guard_hold_streak,
        "guard_targets": guard_targets,
        "why_fast_note": why_fast_note,
        "guard_note": guard_note,
        "next_required_step": (
            _text(
                retry_handoff_summary_payload.get("selected_allatom_next_required_step"),
                selected_krs1_branch_review_next_step,
                retry_handoff_summary_payload.get("selected_krs1_branch_review_next_required_step"),
                dpre1_priority_step,
                _text(
                    retry_handoff_summary_payload.get("selected_rescue_branch_next_required_step"),
                    retry_handoff_summary_payload.get("selected_rescue_review_next_required_step"),
                    tcruzi_pde_rescue_branch_next_step,
                    tcruzi_pde_rescue_review_next_step,
                ),
                dengue_stage6_summary_payload.get("next_required_step") if dengue_stage6_summary_payload else "",
                lbdhodh_validation_next_step
                if lbdhodh_gate51_validated and lbdhodh_validation_next_step
                else "",
                stk17b_followup_review_next_step
                if _text(retry_handoff_summary_payload.get("selected_manual_retry_lane_label")) == "exploratory_gate4.5_followup"
                and stk17b_followup_review_next_step
                else "",
                manual_retry_step if manual_retry_ready and manual_retry_step else "",
                _text(
                    hard_target_rescue_lane_payload.get("next_required_step"),
                    rescue_anchor_artifacts_payload.get("next_required_step"),
                    rescue_three_bead_candidates_payload.get("next_required_step"),
                ),
                (
                    f"Inspect {guard_blocked_target} against the stage6 failure surface before re-enabling auto-start."
                    if guard_active and guard_blocked_target
                    else f"Use success-only rates for {primary_focus or 'the active lane'} and treat held rows as guard churn, not scientific throughput."
                ),
            )
        ),
        "total_shards": total_shards,
    }

    return {
        "title": "Wet-Lab Monitor Semantics",
        "summary": summary,
        "structured": structured,
        "sections": {
            "semantics": "resolved includes both success and hold rows; successful_resolved only counts result_ready rows; held_resolved only counts explicit_hold rows.",
            "rate_interpretation": "rate should be read as success throughput unless you explicitly want guard churn; counterscreen can be compute-attached or supervision-only, so check watcher state before comparing it to primary.",
            "why_fast": why_fast_note,
            "guard": guard_note,
        },
        "rows": rows,
        "markdown": _build_markdown({
            "title": "Wet-Lab Monitor Semantics",
            "summary": summary,
            "structured": structured,
            "rows": rows,
            "sections": {
                "monitor_semantics": "resolved includes both success and hold rows; successful_resolved only counts result_ready rows; held_resolved only counts explicit_hold rows.",
                "rate_interpretation": "rate should be read as success throughput unless you explicitly want guard churn; counterscreen can be compute-attached or supervision-only, so check watcher state before comparing it to primary.",
            },
        }),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab monitor semantics runbook surface.")
    parser.add_argument("--precision-monitor-json", default=DEFAULT_PRECISION_MONITOR_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--antitarget-execution-queue-json", default=DEFAULT_ANTITARGET_EXECUTION_QUEUE_JSON)
    parser.add_argument("--antitarget-progress-json", default=DEFAULT_ANTITARGET_PROGRESS_JSON)
    parser.add_argument("--failure-surface-json", default=DEFAULT_FAILURE_SURFACE_JSON)
    parser.add_argument("--retry-handoff-summary-json", default=DEFAULT_RETRY_HANDOFF_JSON)
    parser.add_argument("--dpre1-branch-review-surface-json", default=DEFAULT_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-branch-review-surface-json", default=DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--dengue-stage6-tuning-surface-json", default=DEFAULT_DENGUE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--dengue-exploratory-retry-lane-json", default=DEFAULT_DENGUE_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--lbdhodh-stage6-tuning-surface-json", default=DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--lbdhodh-exploratory-retry-lane-json", default=DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-rescue-review-surface-json", default=DEFAULT_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--stk17b-manual-retry-lane-json", default=DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-followup-lane-json", default=DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-retry-lane-json", default=DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-followup-review-surface-json", default=DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--plpro-manual-retry-lane-json", default=DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--kinase-retry-policy-templates-json", default=DEFAULT_KINASE_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--target-retry-policy-templates-json", default=DEFAULT_TARGET_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--mapping-fix-retry-policy-templates-json", default=DEFAULT_MAPPING_FIX_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--hard-target-rescue-lane-json", default=DEFAULT_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--rescue-anchor-artifacts-json", default=DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--rescue-three-bead-candidates-json", default=DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--selected-allatom-visual-bundle-json", default=DEFAULT_SELECTED_ALLATOM_VISUAL_BUNDLE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-json", default=DEFAULT_OUT_MD.replace(".md", ".json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.precision_monitor_json),
        load_json(args.execution_queue_json),
        load_json(args.antitarget_execution_queue_json),
        maybe_load_json(args.antitarget_progress_json),
        maybe_load_json(args.failure_surface_json),
        maybe_load_json(args.retry_handoff_summary_json),
        maybe_load_json(args.dpre1_branch_review_surface_json),
        maybe_load_json(args.dengue_stage6_tuning_surface_json),
        maybe_load_json(args.dengue_exploratory_retry_lane_json),
        maybe_load_json(args.lbdhodh_stage6_tuning_surface_json),
        maybe_load_json(args.lbdhodh_exploratory_retry_lane_json),
        maybe_load_json(args.lbdhodh_gate51_validation_review_surface_json),
        maybe_load_json(args.tcruzi_pde_rescue_review_surface_json),
        maybe_load_json(args.tcruzi_pde_promoted_top4_review_packet_json),
        maybe_load_json(args.tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.stk17b_manual_retry_lane_json),
        maybe_load_json(args.stk17b_exploratory_followup_lane_json),
        maybe_load_json(args.stk17b_exploratory_retry_lane_json),
        maybe_load_json(args.stk17b_followup_review_surface_json),
        maybe_load_json(args.plpro_manual_retry_lane_json),
        maybe_load_json(args.kinase_retry_policy_templates_json),
        maybe_load_json(args.target_retry_policy_templates_json),
        maybe_load_json(args.mapping_fix_retry_policy_templates_json),
        maybe_load_json(args.hard_target_rescue_lane_json),
        maybe_load_json(args.rescue_anchor_artifacts_json),
        maybe_load_json(args.rescue_three_bead_candidates_json),
        maybe_load_json(args.tcruzi_krs1_branch_review_surface_json),
        maybe_load_json(args.selected_allatom_visual_bundle_json),
    )
    out_json = resolve(args.out_json)
    out_md = resolve(args.out_md)
    out_json.write_text(__import__("json").dumps({k: v for k, v in payload.items() if k != "markdown"}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(payload["markdown"], encoding="utf-8")


if __name__ == "__main__":
    main()
