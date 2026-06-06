#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HardTargetBranchTemplate:
    branch_key: str
    target_id: str
    branch_label: str
    branch_state: str
    packet_scope: str
    operator_packet_status: str
    branch_summary_status: str
    review_unit_label: str
    selected_command_kind: str
    selected_threshold_a: float
    default_lane_policy: str
    branch_mode: str
    branch_summary_next_step: str
    operator_packet_next_step: str
    operator_packet_surface_label: str


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


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


def build_operator_packet_payload(
    template: HardTargetBranchTemplate,
    *,
    result_summary_payload: dict[str, Any] | None,
    result_review_payload: dict[str, Any] | None,
    run_record_payload: dict[str, Any] | None,
    tuning_surface_payload: dict[str, Any] | None,
    retry_lane_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    result_summary = _summary(result_summary_payload)
    result_review = _summary(result_review_payload)
    run_record = _summary(run_record_payload)
    tuning = _summary(tuning_surface_payload)
    retry_lane = _summary(retry_lane_payload)

    target_id = _text(result_summary.get("target_id"), result_review.get("target_id"), run_record.get("target_id"), tuning.get("target_id"), template.target_id)
    shard_id = _text(retry_lane.get("shard_id"), tuning.get("next_retry_shard_id"), tuning.get("campaign_start_shard_id"))
    selected_command_kind = _text(
        retry_lane.get("selected_command_kind"),
        tuning.get("immediately_runnable_command_kind"),
        template.selected_command_kind,
    )
    selected_threshold_a = _safe_float(
        retry_lane.get("selected_threshold_A"),
        _safe_float(tuning.get("immediately_runnable_threshold_A"), template.selected_threshold_a),
    )
    recommended_threshold_a = _safe_float(
        tuning.get("recommended_observed_threshold_A"),
        selected_threshold_a,
    )
    success_count = _safe_int(retry_lane.get("prior_tuned_success_count"))
    hold_count = _safe_int(retry_lane.get("prior_tuned_hold_count"))
    packet_ready = bool(_text(result_review.get("status"))) and not bool(
        result_review.get("cathepsin_k_explicit_hold", False)
        or result_review.get("dengue_explicit_hold", False)
        or result_review.get("dengue_ns2b_ns3_explicit_hold", False)
        or result_summary.get("explicit_hold", False)
    )

    rows = [
        {
            "row_kind": f"{template.branch_key}_operator_packet_row",
            "target_id": target_id,
            "packet_scope": template.packet_scope,
            "selected_command_kind": selected_command_kind,
            "selected_threshold_A": round(selected_threshold_a, 3),
            "recommended_observed_threshold_A": round(recommended_threshold_a, 3),
            "decision_case": _text(result_summary.get("decision_case")),
            "action": _text(result_summary.get("action")),
            "success_shard_count": success_count,
            "hold_shard_count": hold_count,
            "queue_status_now": _text(result_review.get("queue_status_now"), run_record.get("queue_status_now")),
            "default_lane_reopen_allowed": False,
            "branch_mode": template.branch_mode,
        }
    ]

    return {
        "summary": {
            "status": template.operator_packet_status if packet_ready else f"{template.operator_packet_status[:-6]}empty",
            "target_id": target_id,
            "shard_id": shard_id,
            "surface_label": template.operator_packet_surface_label,
            "packet_scope": template.packet_scope,
            "packet_ready": packet_ready,
            "packet_ready_for_operator_review": packet_ready,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": False,
            "branch_mode": template.branch_mode,
            "review_unit_label": template.review_unit_label,
            "selected_command_kind": selected_command_kind,
            "selected_threshold_A": round(selected_threshold_a, 3),
            "recommended_observed_threshold_A": round(recommended_threshold_a, 3),
            "decision_case": _text(result_summary.get("decision_case")),
            "action": _text(result_summary.get("action")),
            "result_review_ready": bool(_text(result_review.get("status"))),
            "queue_status_now": _text(result_review.get("queue_status_now"), run_record.get("queue_status_now")),
            "success_shard_count": success_count,
            "hold_shard_count": hold_count,
            "next_required_step": template.operator_packet_next_step,
        },
        "structured": {},
        "rows": rows,
    }


def build_branch_summary_payload(
    template: HardTargetBranchTemplate,
    *,
    operator_packet_payload: dict[str, Any] | None,
    result_summary_payload: dict[str, Any] | None,
    result_review_payload: dict[str, Any] | None,
    run_record_payload: dict[str, Any] | None,
    tuning_surface_payload: dict[str, Any] | None,
    retry_lane_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    operator_packet = _summary(operator_packet_payload)
    result_summary = _summary(result_summary_payload)
    result_review = _summary(result_review_payload)
    run_record = _summary(run_record_payload)
    tuning = _summary(tuning_surface_payload)
    retry_lane = _summary(retry_lane_payload)

    target_id = _text(operator_packet.get("target_id"), result_summary.get("target_id"), result_review.get("target_id"), template.target_id)
    shard_id = _text(operator_packet.get("shard_id"), retry_lane.get("shard_id"), tuning.get("next_retry_shard_id"), tuning.get("campaign_start_shard_id"))
    selected_command_kind = _text(operator_packet.get("selected_command_kind"), template.selected_command_kind)
    selected_threshold_a = _safe_float(operator_packet.get("selected_threshold_A"), template.selected_threshold_a)
    success_count = _safe_int(operator_packet.get("success_shard_count"))
    hold_count = _safe_int(operator_packet.get("hold_shard_count"))
    packet_ready = bool(operator_packet.get("packet_ready", False))

    rows = [
        {
            "row_kind": f"{template.branch_key}_branch_step",
            "step_id": "result_summary",
            "status": _text(result_summary.get("status")),
            "signal": _text(result_summary.get("decision_case"), result_summary.get("action")),
        },
        {
            "row_kind": f"{template.branch_key}_branch_step",
            "step_id": "result_review",
            "status": _text(result_review.get("status")),
            "signal": _text(result_review.get("queue_status_now"), run_record.get("queue_status_now")),
        },
        {
            "row_kind": f"{template.branch_key}_branch_step",
            "step_id": "operator_packet",
            "status": _text(operator_packet.get("status")),
            "signal": _text(operator_packet.get("packet_scope"), f"{success_count} success / {hold_count} hold"),
        },
    ]

    return {
        "summary": {
            "status": template.branch_summary_status if packet_ready else f"{template.branch_summary_status[:-6]}pending",
            "target_id": target_id,
            "shard_id": shard_id,
            "branch_label": template.branch_label,
            "branch_state": template.branch_state if packet_ready else "operator_packet_pending_default_lane_closed",
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": False,
            "branch_to_tuned_only": True,
            "review_unit_label": template.review_unit_label,
            "selected_command_kind": selected_command_kind,
            "selected_threshold_A": round(selected_threshold_a, 3),
            "recommended_observed_threshold_A": round(
                _safe_float(operator_packet.get("recommended_observed_threshold_A"), _safe_float(tuning.get("recommended_observed_threshold_A"), selected_threshold_a)),
                3,
            ),
            "decision_case": _text(result_summary.get("decision_case")),
            "action": _text(result_summary.get("action")),
            "operator_packet_ready": packet_ready,
            "operator_packet_scope": _text(operator_packet.get("packet_scope")),
            "success_shard_count": success_count,
            "hold_shard_count": hold_count,
            "result_review_ready": bool(_text(result_review.get("status"))),
            "queue_status_now": _text(result_review.get("queue_status_now"), run_record.get("queue_status_now")),
            "next_required_step": template.branch_summary_next_step,
        },
        "structured": {},
        "rows": rows,
    }
