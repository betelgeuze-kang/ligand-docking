#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_CURRENT_RESULTS_INDEX_JSON = "runs/wetlab_current_results_index_current.json"
DEFAULT_MONITOR_SEMANTICS_JSON = "runs/wetlab_monitor_semantics_current.json"
DEFAULT_DPRE1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_dpre1_branch_review_surface_current.json"
DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_branch_review_surface_current.json"
DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_lbdhodh_stage6_tuning_surface_current.json"
DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_lbdhodh_exploratory_retry_lane_current.json"
DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON = "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_JSON = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.json"
DEFAULT_RESCUE_ONLY_BRANCH_TEMPLATES_JSON = "runs/wetlab_rescue_only_branch_templates_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_RESCUE_LANE_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.json"
DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_REFINEMENT_LANE_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.json"
DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_cathepsin_k_allatom_review_packet_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_REFINEMENT_LANE_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.json"
DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON = "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.json"
DEFAULT_CATHEPSIN_K_TUNED_BRANCH_SUMMARY_JSON = "runs/wetlab_cathepsin_k_tuned_branch_summary_current.json"
DEFAULT_CATHEPSIN_K_TUNED_OPERATOR_PACKET_JSON = "runs/wetlab_cathepsin_k_tuned_operator_packet_current.json"
DEFAULT_DENGUE_REVIEW_BRANCH_SUMMARY_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_review_branch_summary_current.json"
DEFAULT_DENGUE_OPERATOR_PACKET_JSON = "runs/wetlab_dengue_ns2b_ns3_protease_operator_packet_current.json"
DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON = "runs/wetlab_stk17b_manual_retry_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON = "runs/wetlab_stk17b_exploratory_retry_lane_current.json"
DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON = "runs/wetlab_stk17b_exploratory_followup_lane_current.json"
DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON = "runs/wetlab_plpro_manual_retry_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_retry_handoff_summary_current.md"
FOLLOWUP_LANE_LABEL = "exploratory_gate4.5_followup"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _joined(*values: Any, sep: str = " | ", default: str = "") -> str:
    parts = [str(value or "").strip() for value in values if str(value or "").strip()]
    return sep.join(parts) if parts else default


def _unique_targets_in_order(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows:
        target_id = str(row.get("target_id", "")).strip()
        if not target_id or target_id in seen:
            continue
        seen.add(target_id)
        ordered.append(target_id)
    return ordered


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


def _resolve_labeled_value_from_specs(
    specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    *,
    default: Any = None,
    default_source: str = "default",
) -> tuple[Any, str]:
    for source_label, summary, keys in specs:
        if not summary:
            continue
        for key in keys:
            if key not in summary:
                continue
            value = summary.get(key)
            if value is not None and value != "":
                return value, f"{_text(source_label, default='payload')}:{key}"
    return default, default_source


def _normalize_string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = [str(item or "").strip() for item in value]
    else:
        items = [str(value).strip()]
    return [item for item in items if item]


def _gate_readiness_semantics(*sources: str) -> str:
    explicit_keys = {
        "packet_ready_for_operator_review",
        "wetlab_gate_pass",
        "wetlab_final_gate_pass",
        "claim_gate_available",
        "claim_ready_for_allatom",
    }
    legacy_keys = {"packet_ready"}
    normalized = [str(source or "").strip() for source in sources if str(source or "").strip()]
    if any(":" in source and source.split(":", 1)[1] in explicit_keys for source in normalized):
        return "explicit_split_gate_fields"
    if any(":" in source and source.split(":", 1)[1] in legacy_keys for source in normalized):
        return "legacy_packet_ready_fallback"
    if any(source == "legacy_default" for source in normalized):
        return "legacy_default_fallback"
    return "not_reported"


def _first_source_surface_label(*sources: str) -> str:
    for source in sources:
        text = str(source or "").strip()
        if ":" in text:
            return text.split(":", 1)[0]
    return ""


def _resolve_labeled_gate_snapshot(
    *,
    operator_review_specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    wetlab_gate_specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    final_gate_specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    claim_gate_available_specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    claim_ready_specs: list[tuple[str, dict[str, Any] | None, tuple[str, ...]]],
    default_ready: bool = False,
) -> dict[str, Any]:
    operator_default_source = "legacy_default" if default_ready else "default"
    operator_review_value, operator_review_source = _resolve_labeled_value_from_specs(
        operator_review_specs,
        default=default_ready,
        default_source=operator_default_source,
    )
    operator_review_ready = _coerce_boolish(operator_review_value)
    wetlab_default = operator_review_ready if operator_review_ready is not None else default_ready
    wetlab_default_source = operator_review_source if operator_review_source != "default" else operator_default_source
    wetlab_gate_value, wetlab_gate_source = _resolve_labeled_value_from_specs(
        wetlab_gate_specs,
        default=wetlab_default,
        default_source=wetlab_default_source,
    )
    wetlab_gate_pass = _coerce_boolish(wetlab_gate_value)
    final_default = wetlab_gate_pass if wetlab_gate_pass is not None else wetlab_default
    final_default_source = wetlab_gate_source if wetlab_gate_source != "default" else wetlab_default_source
    wetlab_final_gate_value, wetlab_final_gate_source = _resolve_labeled_value_from_specs(
        final_gate_specs,
        default=final_default,
        default_source=final_default_source,
    )
    wetlab_final_gate_pass = _coerce_boolish(wetlab_final_gate_value)
    claim_gate_available_value, claim_gate_source = _resolve_labeled_value_from_specs(
        claim_gate_available_specs,
        default=False,
        default_source="default",
    )
    claim_gate_available = _coerce_boolish(claim_gate_available_value)
    claim_ready_value, claim_ready_source = _resolve_labeled_value_from_specs(
        claim_ready_specs,
        default=False,
        default_source="default",
    )
    claim_ready_for_allatom = _coerce_boolish(claim_ready_value)
    readiness_semantics = _gate_readiness_semantics(
        operator_review_source,
        wetlab_gate_source,
        wetlab_final_gate_source,
        claim_gate_source,
        claim_ready_source,
    )
    return {
        "packet_ready_for_operator_review": bool(operator_review_ready),
        "packet_ready_for_operator_review_source": operator_review_source,
        "wetlab_gate_pass": bool(wetlab_gate_pass),
        "wetlab_gate_source": wetlab_gate_source,
        "wetlab_final_gate_pass": bool(wetlab_final_gate_pass),
        "wetlab_final_gate_source": wetlab_final_gate_source,
        "claim_gate_available": bool(claim_gate_available),
        "claim_gate_source": claim_gate_source,
        "claim_ready_for_allatom": bool(claim_ready_for_allatom),
        "claim_ready_source": claim_ready_source,
        "gate_source_surface_label": _first_source_surface_label(
            wetlab_final_gate_source,
            wetlab_gate_source,
            operator_review_source,
            claim_gate_source,
            claim_ready_source,
        ),
        "readiness_semantics": readiness_semantics,
    }


def _allatom_focus(
    tcruzi_pde_allatom_rescue_lane_payload: dict[str, Any] | None,
    tcruzi_pde_allatom_review_packet_payload: dict[str, Any] | None,
    cathepsin_k_allatom_refinement_lane_payload: dict[str, Any] | None,
    cathepsin_k_allatom_review_packet_payload: dict[str, Any] | None,
    sarscov2_mpro_allatom_refinement_lane_payload: dict[str, Any] | None,
    sarscov2_mpro_allatom_review_packet_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    members = [
        {
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_rescue_lane",
            "surface_kind": "lane",
            "payload": _summary(tcruzi_pde_allatom_rescue_lane_payload),
            "order": 0,
        },
        {
            "target_id": "T. cruzi PDE",
            "surface_label": "tcruzi_pde_allatom_review_packet",
            "surface_kind": "review_packet",
            "payload": _summary(tcruzi_pde_allatom_review_packet_payload),
            "order": 1,
        },
        {
            "target_id": "Cathepsin K",
            "surface_label": "cathepsin_k_allatom_refinement_lane",
            "surface_kind": "lane",
            "payload": _summary(cathepsin_k_allatom_refinement_lane_payload),
            "order": 2,
        },
        {
            "target_id": "Cathepsin K",
            "surface_label": "cathepsin_k_allatom_review_packet",
            "surface_kind": "review_packet",
            "payload": _summary(cathepsin_k_allatom_review_packet_payload),
            "order": 3,
        },
        {
            "target_id": "SARS-CoV-2 Mpro",
            "surface_label": "sarscov2_mpro_allatom_refinement_lane",
            "surface_kind": "lane",
            "payload": _summary(sarscov2_mpro_allatom_refinement_lane_payload),
            "order": 4,
        },
        {
            "target_id": "SARS-CoV-2 Mpro",
            "surface_label": "sarscov2_mpro_allatom_review_packet",
            "surface_kind": "review_packet",
            "payload": _summary(sarscov2_mpro_allatom_review_packet_payload),
            "order": 5,
        },
    ]
    members = [member for member in members if member["payload"]]
    if not members:
        return {
            "ready": False,
            "target_count": 0,
            "surface_count": 0,
            "focus": {},
        }
    focus = min(
        members,
        key=lambda member: (
            0 if member["surface_kind"] == "review_packet" else 1,
            0 if "rescue" in _text(member["payload"].get("packet_scope"), member["payload"].get("branch_mode")) else 1,
            -_safe_int(member["payload"].get("under_2p5_candidate_count"), 0),
            -_safe_int(member["payload"].get("near_candidate_count"), 0),
            _safe_float(member["payload"].get("best_mean_min_distance_A"), 999.0),
            member["order"],
        ),
    )
    focus_payload = dict(focus["payload"])
    focus_target_id = _text(focus_payload.get("target_id"), focus["target_id"])
    review_member_by_target = {
        _text(member["payload"].get("target_id"), member["target_id"]): member
        for member in members
        if member["surface_kind"] == "review_packet"
    }
    lane_member_by_target = {
        _text(member["payload"].get("target_id"), member["target_id"]): member
        for member in members
        if member["surface_kind"] == "lane"
    }
    review_member = review_member_by_target.get(focus_target_id)
    lane_member = lane_member_by_target.get(focus_target_id)
    review_payload = dict((review_member or {}).get("payload") or {})
    lane_payload = dict((lane_member or {}).get("payload") or {})
    default_ready = bool(
        _coerce_boolish(review_payload.get("packet_ready"))
        or _coerce_boolish(focus_payload.get("packet_ready"))
        or _coerce_boolish(lane_payload.get("packet_ready"))
        or _text(review_payload.get("status")).endswith("_ready")
        or _text(focus_payload.get("status")).endswith("_ready")
        or _text(lane_payload.get("status")).endswith("_ready")
    )
    gate_snapshot = _resolve_labeled_gate_snapshot(
        operator_review_specs=[
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
        ],
        wetlab_gate_specs=[
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("wetlab_gate_pass", "packet_ready"),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("wetlab_gate_pass", "packet_ready"),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("wetlab_gate_pass", "packet_ready"),
            ),
        ],
        final_gate_specs=[
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
        ],
        claim_gate_available_specs=[
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("claim_gate_available",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("claim_gate_available",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("claim_gate_available",),
            ),
        ],
        claim_ready_specs=[
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("claim_ready_for_allatom",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("claim_ready_for_allatom",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("claim_ready_for_allatom",),
            ),
        ],
        default_ready=default_ready,
    )
    commercial_schema_version, commercial_schema_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_schema_version",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_schema_version",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_schema_version",),
            ),
        ],
        default="",
    )
    commercial_hard_gate_value, commercial_hard_gate_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_hard_gate_pass_v1",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_hard_gate_pass_v1",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_hard_gate_pass_v1",),
            ),
        ],
        default=False,
    )
    commercial_overall_value, commercial_overall_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_overall_score_v1",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_overall_score_v1",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_overall_score_v1",),
            ),
        ],
        default=None,
    )
    commercial_risk_bucket, commercial_risk_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_risk_bucket_v1",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_risk_bucket_v1",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_risk_bucket_v1",),
            ),
        ],
        default="",
    )
    commercial_decision_class, commercial_decision_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_decision_class_v1",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_decision_class_v1",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_decision_class_v1",),
            ),
        ],
        default="",
    )
    commercial_actions_value, commercial_actions_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_primary_upgrade_actions_v1", "commercial_upgrade_actions_v1"),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_primary_upgrade_actions_v1", "commercial_upgrade_actions_v1"),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_primary_upgrade_actions_v1", "commercial_upgrade_actions_v1"),
            ),
        ],
        default=[],
    )
    commercial_actions = _normalize_string_list(commercial_actions_value)
    commercial_reported = bool(
        _text(commercial_schema_version, commercial_risk_bucket, commercial_decision_class)
        or (commercial_overall_value is not None and commercial_overall_value != "")
        or commercial_actions
        or _coerce_boolish(commercial_hard_gate_value) is not None
    )
    commercial_schema_version_v2, commercial_schema_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_schema_version_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_schema_version_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_schema_version_v2",),
            ),
        ],
        default="",
    )
    commercial_hard_gate_value_v2, commercial_hard_gate_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_hard_gate_pass_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_hard_gate_pass_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_hard_gate_pass_v2",),
            ),
        ],
        default=False,
    )
    commercial_soft_value_v2, commercial_soft_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_soft_score_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_soft_score_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_soft_score_v2",),
            ),
        ],
        default=None,
    )
    commercial_confidence_value_v2, commercial_confidence_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_confidence_score_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_confidence_score_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_confidence_score_v2",),
            ),
        ],
        default=None,
    )
    commercial_overall_value_v2, commercial_overall_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_overall_score_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_overall_score_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_overall_score_v2",),
            ),
        ],
        default=None,
    )
    commercial_risk_bucket_v2, commercial_risk_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_risk_bucket_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_risk_bucket_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_risk_bucket_v2",),
            ),
        ],
        default="",
    )
    commercial_decision_class_v2, commercial_decision_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_decision_class_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_decision_class_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_decision_class_v2",),
            ),
        ],
        default="",
    )
    commercial_actions_value_v2, commercial_actions_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_primary_upgrade_actions_v2", "commercial_upgrade_actions_v2"),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_primary_upgrade_actions_v2", "commercial_upgrade_actions_v2"),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_primary_upgrade_actions_v2", "commercial_upgrade_actions_v2"),
            ),
        ],
        default=[],
    )
    commercial_actions_v2 = _normalize_string_list(commercial_actions_value_v2)
    commercial_human_summary_v2, commercial_human_summary_source_v2 = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("commercial_human_summary_v2",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("commercial_human_summary_v2",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("commercial_human_summary_v2",),
            ),
        ],
        default="",
    )
    commercial_reported_v2 = bool(
        _text(
            commercial_schema_version_v2,
            commercial_risk_bucket_v2,
            commercial_decision_class_v2,
            commercial_human_summary_v2,
        )
        or (commercial_soft_value_v2 is not None and commercial_soft_value_v2 != "")
        or (commercial_confidence_value_v2 is not None and commercial_confidence_value_v2 != "")
        or (commercial_overall_value_v2 is not None and commercial_overall_value_v2 != "")
        or commercial_actions_v2
        or _coerce_boolish(commercial_hard_gate_value_v2) is not None
    )
    translation_gate_version, translation_gate_version_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("translation_gate_version",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("translation_gate_version",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("translation_gate_version",),
            ),
        ],
        default="",
    )
    translation_gate_focus_status, translation_gate_focus_status_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("translation_gate_focus_status",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("translation_gate_focus_status",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("translation_gate_focus_status",),
            ),
        ],
        default="",
    )
    translation_gate_focus_score, translation_gate_focus_score_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("translation_gate_focus_score",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("translation_gate_focus_score",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("translation_gate_focus_score",),
            ),
        ],
        default=None,
    )
    translation_gate_focus_reason, translation_gate_focus_reason_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("translation_gate_focus_reason",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("translation_gate_focus_reason",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("translation_gate_focus_reason",),
            ),
        ],
        default="",
    )
    stronger_physics_shortlist_version, stronger_physics_shortlist_version_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("stronger_physics_shortlist_version",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("stronger_physics_shortlist_version",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("stronger_physics_shortlist_version",),
            ),
        ],
        default="",
    )
    focus_shortlist_tier, focus_shortlist_tier_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("focus_shortlist_tier",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("focus_shortlist_tier",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("focus_shortlist_tier",),
            ),
        ],
        default="",
    )
    recommended_next_expensive_lane, recommended_next_expensive_lane_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("recommended_next_expensive_lane",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("recommended_next_expensive_lane",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("recommended_next_expensive_lane",),
            ),
        ],
        default="",
    )
    recommended_next_expensive_lane_reason, recommended_next_expensive_lane_reason_source = _resolve_labeled_value_from_specs(
        [
            (
                _text((review_member or {}).get("surface_label"), default="review_packet"),
                review_payload,
                ("recommended_next_expensive_lane_reason",),
            ),
            (
                _text(focus.get("surface_label"), default="focus_surface"),
                focus_payload,
                ("recommended_next_expensive_lane_reason",),
            ),
            (
                _text((lane_member or {}).get("surface_label"), default="lane"),
                lane_payload,
                ("recommended_next_expensive_lane_reason",),
            ),
        ],
        default="",
    )
    return {
        "ready": True,
        "target_count": len({_text(member["target_id"]) for member in members if _text(member["target_id"])}),
        "surface_count": len(members),
        "focus": {
            "target_id": focus_target_id,
            "surface_label": focus["surface_label"],
            "surface_kind": focus["surface_kind"],
            "packet_scope": _text(
                focus_payload.get("packet_scope"),
                review_payload.get("packet_scope"),
                lane_payload.get("packet_scope"),
            ),
            "branch_mode": _text(
                focus_payload.get("branch_mode"),
                review_payload.get("branch_mode"),
                lane_payload.get("branch_mode"),
            ),
            "selected_command_kind": _text(
                focus_payload.get("selected_command_kind"),
                review_payload.get("selected_command_kind"),
                lane_payload.get("selected_command_kind"),
            ),
            "selected_threshold_A": _safe_float(focus_payload.get("selected_threshold_A"), 0.0),
            "best_compound_name": _text(
                focus_payload.get("best_compound_name_human_readable"),
                focus_payload.get("best_compound_name"),
                focus_payload.get("best_ligand_id"),
            ),
            "best_compound_name_human_readable": _text(focus_payload.get("best_compound_name_human_readable")),
            "best_compound_name_resolution": _text(
                focus_payload.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "best_mean_min_distance_A": _safe_float(focus_payload.get("best_mean_min_distance_A"), 0.0),
            "promoted_candidate_count": _safe_int(focus_payload.get("promoted_candidate_count"), 0),
            "under_2p5_candidate_count": _safe_int(focus_payload.get("under_2p5_candidate_count"), 0),
            "near_candidate_count": _safe_int(focus_payload.get("near_candidate_count"), 0),
            "next_required_step": _text(
                focus_payload.get("next_required_step"),
                review_payload.get("next_required_step"),
                lane_payload.get("next_required_step"),
            ),
            "status": _text(
                focus_payload.get("status"),
                review_payload.get("status"),
                lane_payload.get("status"),
            ),
            "packet_ready_for_operator_review": bool(gate_snapshot["packet_ready_for_operator_review"]),
            "packet_ready_for_operator_review_source": _text(
                gate_snapshot.get("packet_ready_for_operator_review_source")
            ),
            "wetlab_gate_pass": bool(gate_snapshot["wetlab_gate_pass"]),
            "wetlab_gate_source": _text(gate_snapshot.get("wetlab_gate_source")),
            "wetlab_final_gate_pass": bool(gate_snapshot["wetlab_final_gate_pass"]),
            "wetlab_final_gate_source": _text(gate_snapshot.get("wetlab_final_gate_source")),
            "claim_gate_available": bool(gate_snapshot["claim_gate_available"]),
            "claim_gate_source": _text(gate_snapshot.get("claim_gate_source")),
            "claim_ready_for_allatom": bool(gate_snapshot["claim_ready_for_allatom"]),
            "claim_ready_source": _text(gate_snapshot.get("claim_ready_source")),
            "gate_source_surface_label": _text(gate_snapshot.get("gate_source_surface_label")),
            "readiness_semantics": _text(gate_snapshot.get("readiness_semantics")),
            "commercial_reported_v1": commercial_reported,
            "commercial_schema_version": _text(commercial_schema_version),
            "commercial_hard_gate_pass_v1": bool(_coerce_boolish(commercial_hard_gate_value)),
            "commercial_hard_gate_source_v1": _text(commercial_hard_gate_source),
            "commercial_overall_score_v1": (
                _safe_float(commercial_overall_value)
                if commercial_overall_value is not None and commercial_overall_value != ""
                else 0.0
            ),
            "commercial_overall_source_v1": _text(commercial_overall_source),
            "commercial_risk_bucket_v1": _text(commercial_risk_bucket),
            "commercial_risk_source_v1": _text(commercial_risk_source),
            "commercial_decision_class_v1": _text(commercial_decision_class),
            "commercial_decision_source_v1": _text(commercial_decision_source),
            "commercial_primary_upgrade_actions_v1": commercial_actions,
            "commercial_primary_upgrade_actions_text_v1": " | ".join(commercial_actions),
            "commercial_source_surface_label_v1": _first_source_surface_label(
                commercial_overall_source,
                commercial_risk_source,
                commercial_decision_source,
                commercial_actions_source,
                commercial_hard_gate_source,
                commercial_schema_source,
            ),
            "commercial_reported_v2": commercial_reported_v2,
            "commercial_schema_version_v2": _text(commercial_schema_version_v2),
            "commercial_hard_gate_pass_v2": bool(_coerce_boolish(commercial_hard_gate_value_v2)),
            "commercial_hard_gate_source_v2": _text(commercial_hard_gate_source_v2),
            "commercial_soft_score_v2": (
                _safe_float(commercial_soft_value_v2)
                if commercial_soft_value_v2 is not None and commercial_soft_value_v2 != ""
                else 0.0
            ),
            "commercial_soft_source_v2": _text(commercial_soft_source_v2),
            "commercial_confidence_score_v2": (
                _safe_float(commercial_confidence_value_v2)
                if commercial_confidence_value_v2 is not None and commercial_confidence_value_v2 != ""
                else 0.0
            ),
            "commercial_confidence_source_v2": _text(commercial_confidence_source_v2),
            "commercial_overall_score_v2": (
                _safe_float(commercial_overall_value_v2)
                if commercial_overall_value_v2 is not None and commercial_overall_value_v2 != ""
                else 0.0
            ),
            "commercial_overall_source_v2": _text(commercial_overall_source_v2),
            "commercial_risk_bucket_v2": _text(commercial_risk_bucket_v2),
            "commercial_risk_source_v2": _text(commercial_risk_source_v2),
            "commercial_decision_class_v2": _text(commercial_decision_class_v2),
            "commercial_decision_source_v2": _text(commercial_decision_source_v2),
            "commercial_primary_upgrade_actions_v2": commercial_actions_v2,
            "commercial_primary_upgrade_actions_text_v2": " | ".join(commercial_actions_v2),
            "commercial_human_summary_v2": _text(commercial_human_summary_v2),
            "commercial_human_summary_source_v2": _text(commercial_human_summary_source_v2),
            "commercial_source_surface_label_v2": _first_source_surface_label(
                commercial_overall_source_v2,
                commercial_risk_source_v2,
                commercial_decision_source_v2,
                commercial_actions_source_v2,
                commercial_hard_gate_source_v2,
                commercial_schema_source_v2,
                commercial_human_summary_source_v2,
            ),
            "translation_gate_version": _text(translation_gate_version),
            "translation_gate_version_source": _text(translation_gate_version_source),
            "translation_gate_focus_status": _text(translation_gate_focus_status),
            "translation_gate_focus_status_source": _text(translation_gate_focus_status_source),
            "translation_gate_focus_score": (
                _safe_float(translation_gate_focus_score)
                if translation_gate_focus_score is not None and translation_gate_focus_score != ""
                else 0.0
            ),
            "translation_gate_focus_score_source": _text(translation_gate_focus_score_source),
            "translation_gate_focus_reason": _text(translation_gate_focus_reason),
            "translation_gate_focus_reason_source": _text(translation_gate_focus_reason_source),
            "stronger_physics_shortlist_version": _text(stronger_physics_shortlist_version),
            "stronger_physics_shortlist_version_source": _text(stronger_physics_shortlist_version_source),
            "focus_shortlist_tier": _text(focus_shortlist_tier),
            "focus_shortlist_tier_source": _text(focus_shortlist_tier_source),
            "recommended_next_expensive_lane": _text(recommended_next_expensive_lane),
            "recommended_next_expensive_lane_source": _text(recommended_next_expensive_lane_source),
            "recommended_next_expensive_lane_reason": _text(recommended_next_expensive_lane_reason),
            "recommended_next_expensive_lane_reason_source": _text(
                recommended_next_expensive_lane_reason_source
            ),
        },
    }


def _manual_retry_step_from_plpro_lane(plpro_lane: dict[str, Any] | None) -> str:
    summary = _summary(plpro_lane)
    if not bool(summary.get("ready_for_manual_retry", False)):
        return ""
    shard_id = _text(summary.get("shard_id"))
    selected_kind = _text(summary.get("selected_command_kind"))
    if "gate55" in selected_kind:
        return (
            f"Run the SARS-CoV-2 PLpro tuned gate55 manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
            if shard_id
            else "Run the SARS-CoV-2 PLpro tuned gate55 manual retry runner; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
    return (
        f"Run the SARS-CoV-2 PLpro manual retry runner for {shard_id}; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        if shard_id
        else "Run the SARS-CoV-2 PLpro manual retry runner; keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
    )


def _manual_retry_step_from_lane(lane_payload: dict[str, Any] | None) -> str:
    summary = _summary(lane_payload)
    lane_label_value = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
    followup_selectable = lane_label_value == FOLLOWUP_LANE_LABEL and _text(summary.get("status")).startswith(
        "wetlab_stk17b_exploratory_followup_lane_"
    )
    active_lbdhodh_retry = (
        _text(summary.get("status")).startswith("wetlab_lbdhodh_exploratory_retry_lane_")
        and _text(summary.get("queue_status")) == "running"
        and bool(_text(summary.get("next_required_step")))
    )
    if not bool(summary.get("ready_for_manual_retry", False)) and not followup_selectable and not active_lbdhodh_retry:
        return ""
    target_id = _text(summary.get("target_id"))
    if target_id == "SARS-CoV-2 PLpro":
        return _manual_retry_step_from_plpro_lane(lane_payload)
    explicit_next_step = _text(summary.get("next_required_step"))
    if explicit_next_step:
        return explicit_next_step
    shard_id = _text(summary.get("shard_id"))
    selected_kind = _text(summary.get("selected_command_kind"))
    explicit_label = lane_label_value
    followup_shards = _text(summary.get("followup_shard_ids"))
    if explicit_label == FOLLOWUP_LANE_LABEL or _text(summary.get("hard_freeze_state")) == "hard_freeze_after_exploratory_success":
        lane_label = "exploratory gate4.5 follow-up runner"
    elif "gate45" in selected_kind:
        lane_label = "exploratory gate4.5 manual retry runner"
    elif "gate55" in selected_kind:
        lane_label = "tuned gate55 manual retry runner"
    else:
        lane_label = "manual retry runner"
    if target_id and shard_id:
        freeze_clause = (
            (
                f"keep auto-start hard-frozen after the gate4.5 success and review follow-up shards {followup_shards} separately before reopening."
                if followup_shards
                else "keep auto-start hard-frozen after the gate4.5 success and review the follow-up shards separately before reopening."
            )
            if lane_label == "exploratory gate4.5 follow-up runner"
            else "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
        return f"Run the {target_id} {lane_label} for {shard_id}; {freeze_clause}"
    if target_id:
        freeze_clause = (
            (
                f"keep auto-start hard-frozen after the gate4.5 success and review follow-up shards {followup_shards} separately before reopening."
                if followup_shards
                else "keep auto-start hard-frozen after the gate4.5 success and review the follow-up shards separately before reopening."
            )
            if lane_label == "exploratory gate4.5 follow-up runner"
            else "keep auto-start blocked until the guarded retry either lands a clean summary or is held again."
        )
        return f"Run the {target_id} {lane_label}; {freeze_clause}"
    return ""


def _manual_retry_lane_label(lane_payload: dict[str, Any] | None) -> str:
    summary = _summary(lane_payload)
    explicit = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
    if explicit:
        return explicit
    selected_kind = _text(summary.get("selected_command_kind"))
    if "gate45" in selected_kind:
        return "exploratory_gate45_manual_retry"
    if "gate55" in selected_kind:
        return "tuned_gate55_manual_retry"
    if _text(summary.get("target_id")):
        return "manual_retry"
    return ""


def _lane_shard_display(summary: dict[str, Any]) -> str:
    lane_label = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
    if lane_label == FOLLOWUP_LANE_LABEL:
        return _text(summary.get("shard_id"), summary.get("followup_shard_ids"))
    return _text(summary.get("shard_id"))


def _lane_selectable_for_handoff(lane_payload: dict[str, Any] | None) -> bool:
    summary = _summary(lane_payload)
    if bool(summary.get("ready_for_manual_retry", False)):
        return True
    lane_label = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
    status = _text(summary.get("status"))
    next_step = _text(summary.get("next_required_step"))
    queue_status = _text(summary.get("queue_status"))
    if lane_label == FOLLOWUP_LANE_LABEL and status.startswith("wetlab_stk17b_exploratory_followup_lane_") and bool(next_step):
        return True
    return (
        status.startswith("wetlab_lbdhodh_exploratory_retry_lane_")
        and queue_status == "running"
        and bool(next_step)
    )


def _select_manual_retry_lane(
    monitor_semantics_payload: dict[str, Any],
    retry_handoff_focus_target_id: str,
    *lane_payloads: dict[str, Any] | None,
) -> dict[str, Any]:
    focus_target = _text(
        _summary(monitor_semantics_payload).get("guard_blocked_target_id"),
        retry_handoff_focus_target_id,
    )
    candidates = [payload or {} for payload in lane_payloads if _lane_selectable_for_handoff(payload)]
    if focus_target:
        for payload in candidates:
            if _text(_summary(payload).get("target_id")) == focus_target:
                return payload
    for payload in candidates:
        summary = _summary(payload)
        lane_label = _text(summary.get("followup_lane_label"), summary.get("lane_label"))
        freeze_state = _text(summary.get("hard_freeze_state"), summary.get("freeze_state"))
        if lane_label == FOLLOWUP_LANE_LABEL or freeze_state == "hard_freeze_after_exploratory_success":
            return payload
    return candidates[0] if candidates else {}


def _priority_for_decision(decision: str) -> int:
    mapping = {
        "pause_auto_start": 1,
        "mapping_fix_required": 2,
        "tuned_gate_candidate": 3,
        "do_not_autoadvance": 4,
        "manual_review": 5,
    }
    return mapping.get(str(decision).strip(), 99)


def _retry_rows(retry_preset: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in (retry_preset.get("rows", []) or [])]
    rows.sort(key=lambda row: (_priority_for_decision(str(row.get("recommended_retry_mode", ""))), str(row.get("target_id", "")).strip()))
    normalized: list[dict[str, Any]] = []
    for row in rows:
        target_id = str(row.get("target_id", "")).strip()
        decision = str(row.get("recommended_retry_mode", "")).strip()
        normalized.append(
            {
                "target_id": target_id,
                "decision": decision,
                "source_surface": "retry_preset_surface",
                "source_signal": _joined(
                    f"stage1 {_safe_int(row.get('stage1_mapping_failed_count', 0))}",
                    f"stage6 {_safe_int(row.get('stage6_distance_gate_failed_count', 0))}",
                    f"guard {_text(row.get('consecutive_auto_hold_guard_recommendation'))}",
                ),
                "next_step": _text(row.get("target_specific_next_step")),
            }
        )
    return normalized


def _hold_guard_rows(hold_guard: dict[str, Any], monitor_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    guard_rows = [dict(row) for row in (hold_guard.get("rows", []) or [])]
    guard_rows.sort(
        key=lambda row: (
            0 if bool(row.get("guard_triggered_now", False)) else 1,
            str(row.get("target_id", "")).strip(),
        )
    )
    guard_summary = _summary(hold_guard)
    monitor_summary = _summary(monitor_semantics)
    rows: list[dict[str, Any]] = []
    for row in guard_rows:
        if not bool(row.get("guard_triggered_now", False)):
            continue
        target_id = str(row.get("target_id", "")).strip()
        rows.append(
            {
                "target_id": target_id,
                "decision": "pause_auto_start",
                "source_surface": "hold_guard_surface",
                "source_signal": _joined(
                    f"{_safe_int(row.get('recent_consecutive_auto_hold_streak', 0))} consecutive auto-holds",
                    f"limit {_safe_int(row.get('guard_limit', guard_summary.get('guard_limit', 0)))}",
                    f"focus {_text(monitor_summary.get('guard_blocked_target_id'))}",
                ),
                "next_step": _text(
                    row.get("recommended_policy_action"),
                    default="Pause auto-advance and review the retry preset before reopening the lane.",
                ),
            }
        )
    return rows


def build_payload(
    hold_guard_payload: dict[str, Any],
    retry_preset_payload: dict[str, Any],
    current_results_index_payload: dict[str, Any],
    monitor_semantics_payload: dict[str, Any],
    dpre1_branch_review_surface_payload: dict[str, Any] | None = None,
    tcruzi_krs1_branch_review_surface_payload: dict[str, Any] | None = None,
    lbdhodh_stage6_tuning_surface_payload: dict[str, Any] | None = None,
    lbdhodh_exploratory_retry_lane_payload: dict[str, Any] | None = None,
    lbdhodh_gate51_validation_review_surface_payload: dict[str, Any] | None = None,
    tcruzi_pde_rescue_review_surface_payload: dict[str, Any] | None = None,
    tcruzi_pde_promoted_top4_review_packet_payload: dict[str, Any] | None = None,
    tcruzi_pde_rescue_only_branch_summary_payload: dict[str, Any] | None = None,
    tcruzi_pde_rescue_operator_packet_payload: dict[str, Any] | None = None,
    rescue_only_branch_templates_payload: dict[str, Any] | None = None,
    tcruzi_pde_allatom_rescue_lane_payload: dict[str, Any] | None = None,
    tcruzi_pde_allatom_review_packet_payload: dict[str, Any] | None = None,
    cathepsin_k_allatom_refinement_lane_payload: dict[str, Any] | None = None,
    cathepsin_k_allatom_review_packet_payload: dict[str, Any] | None = None,
    sarscov2_mpro_allatom_refinement_lane_payload: dict[str, Any] | None = None,
    sarscov2_mpro_allatom_review_packet_payload: dict[str, Any] | None = None,
    stk17b_manual_retry_lane_payload: dict[str, Any] | None = None,
    stk17b_exploratory_retry_lane_payload: dict[str, Any] | None = None,
    stk17b_exploratory_followup_lane_payload: dict[str, Any] | None = None,
    stk17b_followup_review_surface_payload: dict[str, Any] | None = None,
    plpro_manual_retry_lane_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hold_summary = _summary(hold_guard_payload)
    retry_summary = _summary(retry_preset_payload)
    index_summary = _summary(current_results_index_payload)
    monitor_summary = _summary(monitor_semantics_payload)
    dpre1_branch_review_summary = _summary(dpre1_branch_review_surface_payload)
    krs1_branch_review_summary = _summary(tcruzi_krs1_branch_review_surface_payload)
    krs1_branch_review_ready = _text(krs1_branch_review_summary.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
    selected_krs1_branch_review_next_step = _text(index_summary.get("selected_krs1_branch_review_next_required_step"))
    lbdhodh_tuning_summary = _summary(lbdhodh_stage6_tuning_surface_payload)
    lbdhodh_lane_summary = _summary(lbdhodh_exploratory_retry_lane_payload)
    lbdhodh_validation_summary = _summary(lbdhodh_gate51_validation_review_surface_payload)
    tcruzi_pde_rescue_review_summary = _summary(tcruzi_pde_rescue_review_surface_payload)
    tcruzi_pde_promoted_top4_review_packet_summary = _summary(tcruzi_pde_promoted_top4_review_packet_payload)
    tcruzi_pde_rescue_only_branch_summary = _summary(tcruzi_pde_rescue_only_branch_summary_payload)
    tcruzi_pde_rescue_operator_packet_summary = _summary(tcruzi_pde_rescue_operator_packet_payload)
    rescue_only_branch_templates_summary = _summary(rescue_only_branch_templates_payload)
    allatom_family = _allatom_focus(
        tcruzi_pde_allatom_rescue_lane_payload,
        tcruzi_pde_allatom_review_packet_payload,
        cathepsin_k_allatom_refinement_lane_payload,
        cathepsin_k_allatom_review_packet_payload,
        sarscov2_mpro_allatom_refinement_lane_payload,
        sarscov2_mpro_allatom_review_packet_payload,
    )
    selected_allatom = dict(allatom_family.get("focus", {}) or {})
    stk17b_lane_summary = _summary(stk17b_manual_retry_lane_payload)
    stk17b_exploratory_lane_summary = _summary(stk17b_exploratory_retry_lane_payload)
    stk17b_exploratory_followup_lane_summary = _summary(stk17b_exploratory_followup_lane_payload)
    stk17b_followup_review_summary = _summary(stk17b_followup_review_surface_payload)
    plpro_lane_summary = _summary(plpro_manual_retry_lane_payload)

    manual_rows = _hold_guard_rows(hold_guard_payload, monitor_semantics_payload) + _retry_rows(retry_preset_payload)
    manual_rows.sort(key=lambda row: (_priority_for_decision(str(row.get("decision", ""))), str(row.get("target_id", "")).strip()))
    for priority, row in enumerate(manual_rows, start=1):
        row["priority_rank"] = priority

    mapping_fix_count = sum(1 for row in manual_rows if str(row.get("decision", "")).strip() == "mapping_fix_required")
    do_not_autoadvance_count = sum(1 for row in manual_rows if str(row.get("decision", "")).strip() == "do_not_autoadvance")
    pause_count = sum(1 for row in manual_rows if str(row.get("decision", "")).strip() == "pause_auto_start")

    priority_targets = " -> ".join(_unique_targets_in_order(manual_rows))
    focus_target_id = str(monitor_summary.get("guard_blocked_target_id", "")).strip()
    focus_row = next((row for row in manual_rows if str(row.get("target_id", "")).strip() == focus_target_id), {})
    selected_lane_payload = _select_manual_retry_lane(
        monitor_semantics_payload,
        focus_target_id,
        lbdhodh_exploratory_retry_lane_payload,
        stk17b_exploratory_followup_lane_payload,
        stk17b_exploratory_retry_lane_payload,
        stk17b_manual_retry_lane_payload,
        plpro_manual_retry_lane_payload,
    )
    selected_lane_summary = _summary(selected_lane_payload)
    selected_manual_retry_step = _manual_retry_step_from_lane(selected_lane_payload)
    selected_manual_retry_lane_label = _manual_retry_lane_label(selected_lane_payload)
    lbdhodh_gate51_validated = bool(
        _text(lbdhodh_validation_summary.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready"
        and bool(lbdhodh_validation_summary.get("gate51_validated", False))
    )
    validated_next_step = (
        _text(lbdhodh_validation_summary.get("next_required_step"))
        if lbdhodh_gate51_validated
        else ""
    )
    tcruzi_pde_rescue_review_ready = bool(
        _text(tcruzi_pde_rescue_review_summary.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready"
    )
    tcruzi_pde_promoted_top4_review_packet_ready = bool(
        _text(tcruzi_pde_promoted_top4_review_packet_summary.get("status"))
        == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
    )
    tcruzi_pde_rescue_only_branch_ready = bool(
        _text(tcruzi_pde_rescue_only_branch_summary.get("status"))
        == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready"
    )
    tcruzi_pde_rescue_operator_packet_ready = bool(
        _text(tcruzi_pde_rescue_operator_packet_summary.get("status"))
        == "wetlab_tcruzi_pde_rescue_operator_packet_ready"
    )
    tcruzi_pde_promoted_top4_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (tcruzi_pde_promoted_top4_review_packet_summary, ("wetlab_gate_pass", "packet_ready")),
            (tcruzi_pde_rescue_operator_packet_summary, ("wetlab_gate_pass", "packet_ready")),
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_gate_available",)),
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_gate_available",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_gate_available", "claim_gate_available"),
            ),
        ],
        claim_ready_specs=[
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_ready_for_allatom",)),
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_ready_for_allatom",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
            ),
        ],
        default_ready=tcruzi_pde_promoted_top4_review_packet_ready,
    )
    tcruzi_pde_rescue_only_branch_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
        ],
        wetlab_gate_specs=[
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tcruzi_pde_rescue_operator_packet_summary, ("wetlab_gate_pass", "packet_ready")),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("wetlab_gate_pass", "packet_ready")),
        ],
        final_gate_specs=[
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
        ],
        claim_gate_available_specs=[
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_gate_available", "claim_gate_available"),
            ),
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_gate_available",)),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_gate_available",)),
        ],
        claim_ready_specs=[
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
            ),
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_ready_for_allatom",)),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_ready_for_allatom",)),
        ],
        default_ready=bool(
            tcruzi_pde_rescue_only_branch_ready
            and (
                bool(tcruzi_pde_rescue_only_branch_summary.get("promoted_top4_packet_ready", False))
                or tcruzi_pde_promoted_top4_gate["packet_ready_for_operator_review"]
            )
        ),
    )
    tcruzi_pde_rescue_operator_packet_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
        ],
        wetlab_gate_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("wetlab_gate_pass", "packet_ready")),
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("wetlab_gate_pass", "packet_ready")),
        ],
        final_gate_specs=[
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
        ],
        claim_gate_available_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_gate_available",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_gate_available", "claim_gate_available"),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_gate_available",)),
        ],
        claim_ready_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_ready_for_allatom",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_ready_for_allatom",)),
        ],
        default_ready=tcruzi_pde_rescue_operator_packet_ready,
    )
    selected_rescue_branch_gate = _resolve_gate_snapshot(
        operator_review_specs=[
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_ready_for_operator_review",
                    "packet_ready_for_operator_review",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("packet_ready_for_operator_review", "packet_ready"),
            ),
        ],
        wetlab_gate_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("wetlab_gate_pass", "packet_ready")),
            (
                tcruzi_pde_rescue_only_branch_summary,
                (
                    "review_packet_wetlab_gate_pass",
                    "wetlab_gate_pass",
                    "review_packet_ready",
                    "promoted_top4_packet_ready",
                    "packet_ready",
                ),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("wetlab_gate_pass", "packet_ready")),
        ],
        final_gate_specs=[
            (
                tcruzi_pde_rescue_operator_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
            (
                tcruzi_pde_rescue_only_branch_summary,
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
            (
                tcruzi_pde_promoted_top4_review_packet_summary,
                ("wetlab_final_gate_pass", "wetlab_gate_pass", "packet_ready"),
            ),
        ],
        claim_gate_available_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_gate_available",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_gate_available", "claim_gate_available"),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_gate_available",)),
        ],
        claim_ready_specs=[
            (tcruzi_pde_rescue_operator_packet_summary, ("claim_ready_for_allatom",)),
            (
                tcruzi_pde_rescue_only_branch_summary,
                ("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
            ),
            (tcruzi_pde_promoted_top4_review_packet_summary, ("claim_ready_for_allatom",)),
        ],
        default_ready=bool(
            tcruzi_pde_rescue_operator_packet_ready
            or tcruzi_pde_rescue_only_branch_gate["packet_ready_for_operator_review"]
            or tcruzi_pde_promoted_top4_gate["packet_ready_for_operator_review"]
        ),
    )
    rescue_only_branch_templates_ready = bool(
        _text(rescue_only_branch_templates_summary.get("status"))
        == "wetlab_rescue_only_branch_templates_ready"
    )
    rescue_operator_next_step = (
        _text(tcruzi_pde_rescue_operator_packet_summary.get("next_required_step"))
        if tcruzi_pde_rescue_operator_packet_ready
        else ""
    )
    rescue_branch_next_step = (
        _text(tcruzi_pde_rescue_only_branch_summary.get("next_required_step"))
        if tcruzi_pde_rescue_only_branch_ready
        else ""
    )
    rescue_review_next_step = _text(
        rescue_branch_next_step,
        rescue_operator_next_step,
        _text(tcruzi_pde_rescue_review_summary.get("next_required_step"))
        if tcruzi_pde_rescue_review_ready
        else "",
    )

    selected_is_stk17b_followup = bool(
        _text(selected_lane_summary.get("target_id")) == "STK17B (DRAK2)"
        and selected_manual_retry_lane_label == FOLLOWUP_LANE_LABEL
    )
    dpre1_branch_review_ready = _text(dpre1_branch_review_summary.get("status")) == "wetlab_dpre1_branch_review_surface_ready"
    dpre1_branch_next_step = _text(
        dpre1_branch_review_summary.get("exploratory_retry_next_required_step"),
        dpre1_branch_review_summary.get("next_required_step"),
    )
    dpre1_priority_step = dpre1_branch_next_step if dpre1_branch_review_ready else ""

    return {
        "summary": {
            "status": "wetlab_retry_handoff_summary_ready",
            "source_surface_count": 4 + (1 if tcruzi_krs1_branch_review_surface_payload is not None else 0),
            "current_results_group_count": _safe_int(index_summary.get("group_count", 0)),
            "current_results_surface_count": _safe_int(index_summary.get("surface_count", 0)),
            "guard_active": bool(monitor_summary.get("guard_active", False)),
            "guard_blocked_target_id": focus_target_id,
            "guard_hold_streak": _safe_int(monitor_summary.get("guard_hold_streak", 0)),
            "guard_limit": _safe_int(hold_summary.get("guard_limit", 0) or monitor_summary.get("guard_limit", 0)),
            "manual_retry_decision_count": len(manual_rows),
            "pause_candidate_count": pause_count,
            "mapping_fix_candidate_count": mapping_fix_count,
            "do_not_autoadvance_candidate_count": do_not_autoadvance_count,
            "manual_retry_priority_targets": priority_targets,
            "manual_retry_focus_target_id": focus_target_id,
            "manual_retry_focus_decision": _text(focus_row.get("decision"), default="pause_auto_start" if focus_target_id else ""),
            "krs1_branch_review_ready": krs1_branch_review_ready,
            "krs1_branch_review_target_id": _text(krs1_branch_review_summary.get("target_id")),
            "krs1_branch_review_branch_label": _text(krs1_branch_review_summary.get("branch_label")),
            "krs1_branch_review_branch_state": _text(krs1_branch_review_summary.get("branch_state")),
            "krs1_branch_review_source_priority": _text(krs1_branch_review_summary.get("source_priority")),
            "krs1_branch_review_decision_source_priority": _text(krs1_branch_review_summary.get("decision_source_priority")),
            "krs1_branch_review_stage6_tuning_surface_ready": bool(
                krs1_branch_review_summary.get("stage6_tuning_surface_ready", False)
            ),
            "krs1_branch_review_stage6_tuning_source_priority": _text(
                krs1_branch_review_summary.get("stage6_tuning_source_priority")
            ),
            "krs1_branch_review_stage6_tuning_recommended_threshold_A": float(
                krs1_branch_review_summary.get("stage6_tuning_recommended_threshold_A", 0.0) or 0.0
            ),
            "krs1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
                krs1_branch_review_summary.get("stage6_tuning_immediately_runnable_command_kind")
            ),
            "krs1_branch_review_stage6_tuning_next_required_step": _text(
                krs1_branch_review_summary.get("stage6_tuning_next_required_step")
            ),
            "krs1_branch_review_exploratory_retry_lane_ready": bool(
                krs1_branch_review_summary.get("exploratory_retry_lane_ready", False)
            ),
            "krs1_branch_review_exploratory_source_priority": _text(
                krs1_branch_review_summary.get("exploratory_source_priority")
            ),
            "krs1_branch_review_exploratory_retry_lane_label": _text(
                krs1_branch_review_summary.get("exploratory_retry_lane_label")
            ),
            "krs1_branch_review_exploratory_retry_selected_command_kind": _text(
                krs1_branch_review_summary.get("exploratory_retry_selected_command_kind")
            ),
            "krs1_branch_review_exploratory_retry_selected_threshold_A": float(
                krs1_branch_review_summary.get("exploratory_retry_selected_threshold_A", 0.0) or 0.0
            ),
            "krs1_branch_review_exploratory_retry_next_required_step": _text(
                krs1_branch_review_summary.get("exploratory_retry_next_required_step")
            ),
            "krs1_branch_review_successor_target": _text(krs1_branch_review_summary.get("successor_target")),
            "krs1_branch_review_successor_gate_state": _text(krs1_branch_review_summary.get("successor_gate_state")),
            "krs1_branch_review_successor_gate_open": bool(krs1_branch_review_summary.get("successor_gate_open", False)),
            "krs1_branch_review_next_required_step": _text(krs1_branch_review_summary.get("next_required_step")),
            "selected_krs1_branch_review_target_id": _text(krs1_branch_review_summary.get("target_id"))
            if selected_krs1_branch_review_next_step
            else "",
            "selected_krs1_branch_review_surface_label": "krs1_branch_review_surface"
            if selected_krs1_branch_review_next_step
            else "",
            "selected_krs1_branch_review_branch_label": _text(krs1_branch_review_summary.get("branch_label"))
            if selected_krs1_branch_review_next_step
            else "",
            "selected_krs1_branch_review_branch_state": _text(krs1_branch_review_summary.get("branch_state"))
            if selected_krs1_branch_review_next_step
            else "",
            "selected_krs1_branch_review_selected_command_kind": _text(
                krs1_branch_review_summary.get("exploratory_retry_selected_command_kind")
            )
            if selected_krs1_branch_review_next_step
            else "",
            "selected_krs1_branch_review_selected_threshold_A": float(
                krs1_branch_review_summary.get("exploratory_retry_selected_threshold_A", 0.0) or 0.0
            )
            if selected_krs1_branch_review_next_step
            else 0.0,
            "selected_krs1_branch_review_next_required_step": selected_krs1_branch_review_next_step,
            "dpre1_branch_review_ready": dpre1_branch_review_ready,
            "dpre1_branch_review_target_id": _text(dpre1_branch_review_summary.get("target_id")),
            "dpre1_branch_review_branch_label": _text(dpre1_branch_review_summary.get("branch_label")),
            "dpre1_branch_review_branch_state": _text(dpre1_branch_review_summary.get("branch_state")),
            "dpre1_branch_review_source_priority": _text(dpre1_branch_review_summary.get("source_priority")),
            "dpre1_branch_review_decision_source_priority": _text(dpre1_branch_review_summary.get("decision_source_priority")),
            "dpre1_branch_review_result_review_status": _text(dpre1_branch_review_summary.get("result_review_status")),
            "dpre1_branch_review_result_summary_status": _text(dpre1_branch_review_summary.get("result_summary_status")),
            "dpre1_branch_review_launch_packet_status": _text(dpre1_branch_review_summary.get("launch_packet_status")),
            "dpre1_branch_review_stage6_tuning_surface_ready": bool(
                dpre1_branch_review_summary.get("stage6_tuning_surface_ready", False)
            ),
            "dpre1_branch_review_stage6_tuning_source_priority": _text(
                dpre1_branch_review_summary.get("stage6_tuning_source_priority")
            ),
            "dpre1_branch_review_stage6_tuning_recommended_threshold_A": float(
                dpre1_branch_review_summary.get("stage6_tuning_recommended_threshold_A", 0.0) or 0.0
            ),
            "dpre1_branch_review_stage6_tuning_immediately_runnable_command_kind": _text(
                dpre1_branch_review_summary.get("stage6_tuning_immediately_runnable_command_kind")
            ),
            "dpre1_branch_review_exploratory_retry_lane_ready": bool(
                dpre1_branch_review_summary.get("exploratory_retry_lane_ready", False)
            ),
            "dpre1_branch_review_exploratory_source_priority": _text(
                dpre1_branch_review_summary.get("exploratory_source_priority")
            ),
            "dpre1_branch_review_exploratory_retry_lane_label": _text(
                dpre1_branch_review_summary.get("exploratory_retry_lane_label")
            ),
            "dpre1_branch_review_exploratory_retry_selected_command_kind": _text(
                dpre1_branch_review_summary.get("exploratory_retry_selected_command_kind")
            ),
            "dpre1_branch_review_exploratory_retry_selected_threshold_A": float(
                dpre1_branch_review_summary.get("exploratory_retry_selected_threshold_A", 0.0) or 0.0
            ),
            "dpre1_branch_review_successor_target": _text(dpre1_branch_review_summary.get("successor_target")),
            "dpre1_branch_review_successor_gate_state": _text(dpre1_branch_review_summary.get("successor_gate_state")),
            "dpre1_branch_review_next_required_step": dpre1_branch_next_step,
            "selected_krs1_branch_review_target_id": _text(
                index_summary.get("selected_krs1_branch_review_target_id"),
                krs1_branch_review_summary.get("target_id") if selected_krs1_branch_review_next_step else "",
            ),
            "selected_krs1_branch_review_surface_label": _text(
                index_summary.get("selected_krs1_branch_review_surface_label"),
                "krs1_branch_review_surface" if selected_krs1_branch_review_next_step else "",
            ),
            "selected_krs1_branch_review_branch_label": _text(
                index_summary.get("selected_krs1_branch_review_branch_label"),
                krs1_branch_review_summary.get("branch_label") if selected_krs1_branch_review_next_step else "",
            ),
            "selected_krs1_branch_review_branch_state": _text(
                index_summary.get("selected_krs1_branch_review_branch_state"),
                krs1_branch_review_summary.get("branch_state") if selected_krs1_branch_review_next_step else "",
            ),
            "selected_krs1_branch_review_selected_command_kind": _text(
                index_summary.get("selected_krs1_branch_review_selected_command_kind"),
                krs1_branch_review_summary.get("exploratory_retry_selected_command_kind")
                if selected_krs1_branch_review_next_step
                else "",
            ),
            "selected_krs1_branch_review_selected_threshold_A": _safe_float(
                index_summary.get("selected_krs1_branch_review_selected_threshold_A"),
                _safe_float(krs1_branch_review_summary.get("exploratory_retry_selected_threshold_A"), 0.0)
                if selected_krs1_branch_review_next_step
                else 0.0,
            ),
            "selected_krs1_branch_review_next_required_step": selected_krs1_branch_review_next_step,
            "lbdhodh_stage6_tuning_surface_ready": _text(lbdhodh_tuning_summary.get("status")) == "wetlab_lbdhodh_stage6_tuning_surface_ready",
            "lbdhodh_stage6_tuning_next_retry_shard_id": _text(lbdhodh_tuning_summary.get("next_retry_shard_id")),
            "lbdhodh_stage6_tuning_recommended_observed_threshold_A": float(
                lbdhodh_tuning_summary.get("recommended_observed_threshold_A", 0.0) or 0.0
            ),
            "lbdhodh_stage6_tuning_immediately_runnable_command_kind": _text(
                lbdhodh_tuning_summary.get("immediately_runnable_command_kind")
            ),
            "lbdhodh_gate51_validation_review_surface_ready": _text(lbdhodh_validation_summary.get("status")) == "wetlab_lbdhodh_gate51_validation_review_surface_ready",
            "lbdhodh_gate51_validated": lbdhodh_gate51_validated,
            "lbdhodh_gate51_validation_decision": _text(lbdhodh_validation_summary.get("decision")),
            "lbdhodh_gate51_validation_default_lane_reopen_allowed": bool(
                lbdhodh_validation_summary.get("default_lane_reopen_allowed", False)
            ),
            "lbdhodh_gate51_validation_branch_to_gate51_only": bool(
                lbdhodh_validation_summary.get("branch_to_gate51_only", False)
            ),
            "lbdhodh_gate51_validation_validated_command_kind": _text(
                lbdhodh_validation_summary.get("validated_command_kind")
            ),
            "lbdhodh_gate51_validation_validated_threshold_A": float(
                lbdhodh_validation_summary.get("validated_threshold_A", 0.0) or 0.0
            ),
            "lbdhodh_gate51_validation_success_count": _safe_int(
                lbdhodh_validation_summary.get("gate51_validation_success_count", 0)
            ),
            "lbdhodh_gate51_validation_row_count": _safe_int(
                lbdhodh_validation_summary.get("gate51_validation_row_count", 0)
            ),
            "tcruzi_pde_rescue_review_surface_ready": tcruzi_pde_rescue_review_ready,
            "tcruzi_pde_rescue_review_decision": _text(tcruzi_pde_rescue_review_summary.get("decision")),
            "tcruzi_pde_rescue_review_default_lane_reopen_allowed": bool(
                tcruzi_pde_rescue_review_summary.get("default_lane_reopen_allowed", False)
            ),
            "tcruzi_pde_rescue_review_branch_to_rescue_only": bool(
                tcruzi_pde_rescue_review_summary.get("branch_to_rescue_only", False)
            ),
            "tcruzi_pde_rescue_review_promoted_candidate_count": _safe_int(
                tcruzi_pde_rescue_review_summary.get("promoted_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_review_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_rescue_review_summary.get("under_2p5_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_review_near_candidate_count": _safe_int(
                tcruzi_pde_rescue_review_summary.get("near_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_review_selected_command_kind": _text(
                tcruzi_pde_rescue_review_summary.get("selected_command_kind")
            ),
            "tcruzi_pde_rescue_review_selected_threshold_A": float(
                tcruzi_pde_rescue_review_summary.get("selected_threshold_A", 0.0) or 0.0
            ),
            "tcruzi_pde_promoted_top4_review_packet_ready": tcruzi_pde_promoted_top4_review_packet_ready,
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
            "tcruzi_pde_promoted_top4_review_packet_target_id": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("target_id")
            ),
            "tcruzi_pde_promoted_top4_review_packet_shard_id": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("shard_id")
            ),
            "tcruzi_pde_promoted_top4_review_packet_scope": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("packet_scope")
            ),
            "tcruzi_pde_promoted_top4_review_packet_selected_command_kind": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("selected_command_kind")
            ),
            "tcruzi_pde_promoted_top4_review_packet_strict_threshold_A": float(
                tcruzi_pde_promoted_top4_review_packet_summary.get("strict_threshold_A", 0.0) or 0.0
            ),
            "tcruzi_pde_promoted_top4_review_packet_near_threshold_A": float(
                tcruzi_pde_promoted_top4_review_packet_summary.get("near_threshold_A", 0.0) or 0.0
            ),
            "tcruzi_pde_promoted_top4_review_packet_promoted_candidate_count": _safe_int(
                tcruzi_pde_promoted_top4_review_packet_summary.get("promoted_candidate_count", 0)
            ),
            "tcruzi_pde_promoted_top4_review_packet_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_promoted_top4_review_packet_summary.get("under_2p5_candidate_count", 0)
            ),
            "tcruzi_pde_promoted_top4_review_packet_near_candidate_count": _safe_int(
                tcruzi_pde_promoted_top4_review_packet_summary.get("near_candidate_count", 0)
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_ligand_id": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_ligand_id")
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_ligand_id"),
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name_human_readable": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable")
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_compound_name_resolution": _text(
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "tcruzi_pde_promoted_top4_review_packet_best_mean_min_distance_A": float(
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_mean_min_distance_A", 0.0) or 0.0
            ),
            "tcruzi_pde_rescue_only_branch_summary_ready": tcruzi_pde_rescue_only_branch_ready,
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
            "tcruzi_pde_rescue_only_branch_target_id": _text(tcruzi_pde_rescue_only_branch_summary.get("target_id")),
            "tcruzi_pde_rescue_only_branch_shard_id": _text(tcruzi_pde_rescue_only_branch_summary.get("shard_id")),
            "tcruzi_pde_rescue_only_branch_label": _text(tcruzi_pde_rescue_only_branch_summary.get("branch_label")),
            "tcruzi_pde_rescue_only_branch_state": _text(tcruzi_pde_rescue_only_branch_summary.get("branch_state")),
            "tcruzi_pde_rescue_only_branch_default_lane_reopen_allowed": bool(
                tcruzi_pde_rescue_only_branch_summary.get("default_lane_reopen_allowed", False)
            ),
            "tcruzi_pde_rescue_only_branch_branch_to_rescue_only": bool(
                tcruzi_pde_rescue_only_branch_summary.get("branch_to_rescue_only", False)
            ),
            "tcruzi_pde_rescue_only_branch_selected_command_kind": _text(
                tcruzi_pde_rescue_only_branch_summary.get("selected_command_kind")
            ),
            "tcruzi_pde_rescue_only_branch_selected_threshold_A": float(
                tcruzi_pde_rescue_only_branch_summary.get("selected_threshold_A", 0.0) or 0.0
            ),
            "tcruzi_pde_rescue_only_branch_promoted_top4_packet_ready": bool(
                tcruzi_pde_rescue_only_branch_summary.get("promoted_top4_packet_ready", False)
            ),
            "tcruzi_pde_rescue_only_branch_promoted_candidate_count": _safe_int(
                tcruzi_pde_rescue_only_branch_summary.get("promoted_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_only_branch_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_rescue_only_branch_summary.get("under_2p5_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_only_branch_near_candidate_count": _safe_int(
                tcruzi_pde_rescue_only_branch_summary.get("near_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_only_branch_best_ligand_id": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_ligand_id")
            ),
            "tcruzi_pde_rescue_only_branch_best_compound_name": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name"),
                tcruzi_pde_rescue_only_branch_summary.get("best_ligand_id"),
            ),
            "tcruzi_pde_rescue_only_branch_best_compound_name_human_readable": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_human_readable")
            ),
            "tcruzi_pde_rescue_only_branch_best_compound_name_resolution": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "tcruzi_pde_rescue_only_branch_best_mean_min_distance_A": float(
                tcruzi_pde_rescue_only_branch_summary.get("best_mean_min_distance_A", 0.0) or 0.0
            ),
            "selected_rescue_review_best_compound_name": _text(
                tcruzi_pde_rescue_review_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_rescue_review_summary.get("best_compound_name"),
                tcruzi_pde_rescue_review_summary.get("best_ligand_id"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_ligand_id"),
            ),
            "selected_rescue_review_best_compound_name_human_readable": _text(
                tcruzi_pde_rescue_review_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable"),
            ),
            "selected_rescue_review_best_compound_name_resolution": _text(
                tcruzi_pde_rescue_review_summary.get("best_compound_name_resolution"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "tcruzi_pde_rescue_operator_packet_ready": tcruzi_pde_rescue_operator_packet_ready,
            "tcruzi_pde_rescue_operator_packet_operator_review_ready": tcruzi_pde_rescue_operator_packet_gate[
                "packet_ready_for_operator_review"
            ],
            "tcruzi_pde_rescue_operator_packet_wetlab_gate_pass": tcruzi_pde_rescue_operator_packet_gate[
                "wetlab_gate_pass"
            ],
            "tcruzi_pde_rescue_operator_packet_wetlab_final_gate_pass": tcruzi_pde_rescue_operator_packet_gate[
                "wetlab_final_gate_pass"
            ],
            "tcruzi_pde_rescue_operator_packet_claim_gate_available": tcruzi_pde_rescue_operator_packet_gate[
                "claim_gate_available"
            ],
            "tcruzi_pde_rescue_operator_packet_claim_ready_for_allatom": tcruzi_pde_rescue_operator_packet_gate[
                "claim_ready_for_allatom"
            ],
            "tcruzi_pde_rescue_operator_packet_target_id": _text(
                tcruzi_pde_rescue_operator_packet_summary.get("target_id")
            ),
            "tcruzi_pde_rescue_operator_packet_shard_id": _text(
                tcruzi_pde_rescue_operator_packet_summary.get("shard_id")
            ),
            "tcruzi_pde_rescue_operator_packet_scope": _text(
                tcruzi_pde_rescue_operator_packet_summary.get("packet_scope")
            ),
            "tcruzi_pde_rescue_operator_packet_selected_command_kind": _text(
                tcruzi_pde_rescue_operator_packet_summary.get("selected_command_kind")
            ),
            "tcruzi_pde_rescue_operator_packet_selected_threshold_A": float(
                tcruzi_pde_rescue_operator_packet_summary.get("selected_threshold_A", 0.0) or 0.0
            ),
            "tcruzi_pde_rescue_operator_packet_promoted_candidate_count": _safe_int(
                tcruzi_pde_rescue_operator_packet_summary.get("promoted_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_operator_packet_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_rescue_operator_packet_summary.get("under_2p5_candidate_count", 0)
            ),
            "tcruzi_pde_rescue_operator_packet_next_required_step": rescue_operator_next_step,
            "selected_rescue_branch_best_compound_name": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name"),
                tcruzi_pde_rescue_only_branch_summary.get("best_ligand_id"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_ligand_id"),
            ),
            "selected_rescue_branch_best_compound_name_human_readable": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_human_readable"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_human_readable"),
            ),
            "selected_rescue_branch_best_compound_name_resolution": _text(
                tcruzi_pde_rescue_only_branch_summary.get("best_compound_name_resolution"),
                tcruzi_pde_promoted_top4_review_packet_summary.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "rescue_only_branch_templates_ready": rescue_only_branch_templates_ready,
            "rescue_only_branch_template_target_count": _safe_int(
                rescue_only_branch_templates_summary.get("template_target_count", 0)
            ),
            "rescue_only_branch_focus_target_id": _text(
                rescue_only_branch_templates_summary.get("focus_target_id")
            ),
            "rescue_only_branch_focus_template_label": _text(
                rescue_only_branch_templates_summary.get("focus_template_label")
            ),
            "rescue_only_branch_focus_surface_label": _text(
                rescue_only_branch_templates_summary.get("focus_surface_label")
            ),
            "rescue_only_branch_focus_selected_command_kind": _text(
                rescue_only_branch_templates_summary.get("focus_selected_command_kind")
            ),
            "rescue_only_branch_focus_selected_threshold_A": float(
                rescue_only_branch_templates_summary.get("focus_selected_threshold_A", 0.0) or 0.0
            ),
            "lbdhodh_exploratory_retry_target_id": _text(lbdhodh_lane_summary.get("target_id")),
            "lbdhodh_exploratory_retry_shard_id": _text(lbdhodh_lane_summary.get("shard_id")),
            "lbdhodh_exploratory_retry_selected_command_kind": _text(lbdhodh_lane_summary.get("selected_command_kind")),
            "lbdhodh_exploratory_retry_lane_label": _text(
                lbdhodh_lane_summary.get("lane_label"),
                lbdhodh_lane_summary.get("followup_lane_label"),
            ),
            "stk17b_manual_retry_target_id": _text(stk17b_lane_summary.get("target_id")),
            "stk17b_manual_retry_shard_id": _text(stk17b_lane_summary.get("shard_id")),
            "stk17b_manual_retry_selected_command_kind": _text(stk17b_lane_summary.get("selected_command_kind")),
            "stk17b_exploratory_retry_target_id": _text(stk17b_exploratory_lane_summary.get("target_id")),
            "stk17b_exploratory_retry_shard_id": _text(stk17b_exploratory_lane_summary.get("shard_id")),
            "stk17b_exploratory_retry_selected_command_kind": _text(stk17b_exploratory_lane_summary.get("selected_command_kind")),
            "stk17b_exploratory_followup_target_id": _text(stk17b_exploratory_followup_lane_summary.get("target_id")),
            "stk17b_exploratory_followup_shard_id": _lane_shard_display(stk17b_exploratory_followup_lane_summary),
            "stk17b_exploratory_followup_selected_command_kind": _text(stk17b_exploratory_followup_lane_summary.get("selected_command_kind")),
            "stk17b_exploratory_followup_lane_label": _text(
                stk17b_exploratory_followup_lane_summary.get("followup_lane_label"),
                stk17b_exploratory_followup_lane_summary.get("lane_label"),
            ),
            "stk17b_exploratory_followup_freeze_state": _text(
                stk17b_exploratory_followup_lane_summary.get("freeze_state"),
                stk17b_exploratory_followup_lane_summary.get("hard_freeze_state"),
            ),
            "stk17b_exploratory_followup_freeze_note": _text(stk17b_exploratory_followup_lane_summary.get("freeze_note")),
            "stk17b_exploratory_followup_followup_shard_ids": _text(
                stk17b_exploratory_followup_lane_summary.get("followup_shard_ids")
            ),
            "stk17b_followup_review_surface_ready": _text(stk17b_followup_review_summary.get("status")) == "wetlab_stk17b_followup_review_surface_ready",
            "stk17b_followup_review_decision": _text(stk17b_followup_review_summary.get("decision")),
            "stk17b_followup_review_default_lane_reopen_allowed": bool(
                stk17b_followup_review_summary.get("default_lane_reopen_allowed", False)
            ),
            "stk17b_followup_review_branch_to_gate45_only": bool(
                stk17b_followup_review_summary.get("branch_to_gate45_only", False)
            ),
            "plpro_manual_retry_target_id": _text(plpro_lane_summary.get("target_id")),
            "plpro_manual_retry_shard_id": _text(plpro_lane_summary.get("shard_id")),
            "plpro_manual_retry_selected_command_kind": _text(plpro_lane_summary.get("selected_command_kind")),
            "selected_validated_target_id": _text(lbdhodh_validation_summary.get("target_id")) if lbdhodh_gate51_validated else "",
            "selected_validated_surface_label": "gate5.1_validation_review" if lbdhodh_gate51_validated else "",
            "selected_validated_selected_command_kind": _text(lbdhodh_validation_summary.get("validated_command_kind")) if lbdhodh_gate51_validated else "",
            "selected_validated_threshold_A": float(lbdhodh_validation_summary.get("validated_threshold_A", 0.0) or 0.0) if lbdhodh_gate51_validated else 0.0,
            "selected_validated_next_required_step": validated_next_step,
            "selected_rescue_review_target_id": _text(tcruzi_pde_rescue_review_summary.get("target_id")) if tcruzi_pde_rescue_review_ready else "",
            "selected_rescue_review_surface_label": "pde_rescue_review" if tcruzi_pde_rescue_review_ready else "",
            "selected_rescue_review_selected_command_kind": _text(tcruzi_pde_rescue_review_summary.get("selected_command_kind")) if tcruzi_pde_rescue_review_ready else "",
            "selected_rescue_review_strict_threshold_A": float(tcruzi_pde_rescue_review_summary.get("strict_threshold_A", 0.0) or 0.0) if tcruzi_pde_rescue_review_ready else 0.0,
            "selected_rescue_review_near_threshold_A": float(tcruzi_pde_rescue_review_summary.get("near_threshold_A", 0.0) or 0.0) if tcruzi_pde_rescue_review_ready else 0.0,
            "selected_rescue_review_promoted_candidate_count": _safe_int(
                tcruzi_pde_rescue_review_summary.get("promoted_candidate_count", 0)
            ) if tcruzi_pde_rescue_review_ready else 0,
            "selected_rescue_review_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_rescue_review_summary.get("under_2p5_candidate_count", 0)
            ) if tcruzi_pde_rescue_review_ready else 0,
            "selected_rescue_review_next_required_step": rescue_review_next_step,
            "selected_rescue_branch_target_id": _text(
                tcruzi_pde_rescue_only_branch_summary.get("target_id")
            ) if tcruzi_pde_rescue_only_branch_ready else "",
            "selected_rescue_branch_surface_label": "pde_rescue_only_branch" if tcruzi_pde_rescue_only_branch_ready else "",
            "selected_rescue_branch_selected_command_kind": _text(
                tcruzi_pde_rescue_only_branch_summary.get("selected_command_kind")
            ) if tcruzi_pde_rescue_only_branch_ready else "",
            "selected_rescue_branch_selected_threshold_A": float(
                tcruzi_pde_rescue_only_branch_summary.get("selected_threshold_A", 0.0) or 0.0
            ) if tcruzi_pde_rescue_only_branch_ready else 0.0,
            "selected_rescue_branch_promoted_candidate_count": _safe_int(
                tcruzi_pde_rescue_only_branch_summary.get("promoted_candidate_count", 0)
            ) if tcruzi_pde_rescue_only_branch_ready else 0,
            "selected_rescue_branch_under_2p5_candidate_count": _safe_int(
                tcruzi_pde_rescue_only_branch_summary.get("under_2p5_candidate_count", 0)
            ) if tcruzi_pde_rescue_only_branch_ready else 0,
            "selected_rescue_branch_operator_review_ready": selected_rescue_branch_gate[
                "packet_ready_for_operator_review"
            ],
            "selected_rescue_branch_wetlab_gate_pass": selected_rescue_branch_gate["wetlab_gate_pass"],
            "selected_rescue_branch_wetlab_final_gate_pass": selected_rescue_branch_gate[
                "wetlab_final_gate_pass"
            ],
            "selected_rescue_branch_claim_gate_available": selected_rescue_branch_gate["claim_gate_available"],
            "selected_rescue_branch_claim_ready_for_allatom": selected_rescue_branch_gate[
                "claim_ready_for_allatom"
            ],
            "selected_rescue_branch_operator_packet_ready": tcruzi_pde_rescue_operator_packet_gate[
                "packet_ready_for_operator_review"
            ],
            "selected_rescue_branch_operator_packet_wetlab_gate_pass": tcruzi_pde_rescue_operator_packet_gate[
                "wetlab_gate_pass"
            ],
            "selected_rescue_branch_operator_packet_wetlab_final_gate_pass": tcruzi_pde_rescue_operator_packet_gate[
                "wetlab_final_gate_pass"
            ],
            "selected_rescue_branch_operator_packet_claim_gate_available": tcruzi_pde_rescue_operator_packet_gate[
                "claim_gate_available"
            ],
            "selected_rescue_branch_operator_packet_claim_ready_for_allatom": tcruzi_pde_rescue_operator_packet_gate[
                "claim_ready_for_allatom"
            ],
            "selected_rescue_branch_operator_packet_scope": _text(
                tcruzi_pde_rescue_operator_packet_summary.get("packet_scope")
            ) if tcruzi_pde_rescue_operator_packet_gate["packet_ready_for_operator_review"] else "",
            "allatom_family_ready": bool(allatom_family.get("ready", False)),
            "allatom_family_target_count": _safe_int(allatom_family.get("target_count"), 0),
            "allatom_family_surface_count": _safe_int(allatom_family.get("surface_count"), 0),
            "allatom_family_focus_target_id": _text(selected_allatom.get("target_id")),
            "allatom_family_focus_surface_label": _text(selected_allatom.get("surface_label")),
            "allatom_family_focus_packet_scope": _text(selected_allatom.get("packet_scope")),
            "allatom_family_focus_selected_command_kind": _text(selected_allatom.get("selected_command_kind")),
            "allatom_family_focus_selected_threshold_A": _safe_float(selected_allatom.get("selected_threshold_A"), 0.0),
            "allatom_family_focus_packet_ready_for_operator_review": bool(
                selected_allatom.get("packet_ready_for_operator_review", False)
            ),
            "allatom_family_focus_operator_review_ready": bool(
                selected_allatom.get("packet_ready_for_operator_review", False)
            ),
            "allatom_family_focus_packet_ready_for_operator_review_source": _text(
                selected_allatom.get("packet_ready_for_operator_review_source")
            ),
            "allatom_family_focus_operator_review_ready_source": _text(
                selected_allatom.get("packet_ready_for_operator_review_source")
            ),
            "allatom_family_focus_wetlab_gate_pass": bool(selected_allatom.get("wetlab_gate_pass", False)),
            "allatom_family_focus_wetlab_gate_source": _text(selected_allatom.get("wetlab_gate_source")),
            "allatom_family_focus_wetlab_final_gate_pass": bool(
                selected_allatom.get("wetlab_final_gate_pass", False)
            ),
            "allatom_family_focus_wetlab_final_gate_source": _text(
                selected_allatom.get("wetlab_final_gate_source")
            ),
            "allatom_family_focus_claim_gate_available": bool(
                selected_allatom.get("claim_gate_available", False)
            ),
            "allatom_family_focus_claim_gate_source": _text(selected_allatom.get("claim_gate_source")),
            "allatom_family_focus_claim_ready_for_allatom": bool(
                selected_allatom.get("claim_ready_for_allatom", False)
            ),
            "allatom_family_focus_claim_ready_source": _text(selected_allatom.get("claim_ready_source")),
            "allatom_family_focus_gate_source_surface_label": _text(
                selected_allatom.get("gate_source_surface_label")
            ),
            "allatom_family_focus_readiness_semantics": _text(selected_allatom.get("readiness_semantics")),
            "allatom_family_focus_commercial_reported_v1": bool(
                selected_allatom.get("commercial_reported_v1", False)
            ),
            "allatom_family_focus_commercial_schema_version": _text(
                selected_allatom.get("commercial_schema_version")
            ),
            "allatom_family_focus_commercial_hard_gate_pass_v1": bool(
                selected_allatom.get("commercial_hard_gate_pass_v1", False)
            ),
            "allatom_family_focus_commercial_hard_gate_source_v1": _text(
                selected_allatom.get("commercial_hard_gate_source_v1")
            ),
            "allatom_family_focus_commercial_overall_score_v1": _safe_float(
                selected_allatom.get("commercial_overall_score_v1"),
                0.0,
            ),
            "allatom_family_focus_commercial_overall_source_v1": _text(
                selected_allatom.get("commercial_overall_source_v1")
            ),
            "allatom_family_focus_commercial_risk_bucket_v1": _text(
                selected_allatom.get("commercial_risk_bucket_v1")
            ),
            "allatom_family_focus_commercial_risk_source_v1": _text(
                selected_allatom.get("commercial_risk_source_v1")
            ),
            "allatom_family_focus_commercial_decision_class_v1": _text(
                selected_allatom.get("commercial_decision_class_v1")
            ),
            "allatom_family_focus_commercial_decision_source_v1": _text(
                selected_allatom.get("commercial_decision_source_v1")
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_v1": list(
                selected_allatom.get("commercial_primary_upgrade_actions_v1", []) or []
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_text_v1": _text(
                selected_allatom.get("commercial_primary_upgrade_actions_text_v1")
            ),
            "allatom_family_focus_commercial_source_surface_label_v1": _text(
                selected_allatom.get("commercial_source_surface_label_v1")
            ),
            "allatom_family_focus_commercial_reported_v2": bool(
                selected_allatom.get("commercial_reported_v2", False)
            ),
            "allatom_family_focus_commercial_schema_version_v2": _text(
                selected_allatom.get("commercial_schema_version_v2")
            ),
            "allatom_family_focus_commercial_hard_gate_pass_v2": bool(
                selected_allatom.get("commercial_hard_gate_pass_v2", False)
            ),
            "allatom_family_focus_commercial_hard_gate_source_v2": _text(
                selected_allatom.get("commercial_hard_gate_source_v2")
            ),
            "allatom_family_focus_commercial_soft_score_v2": _safe_float(
                selected_allatom.get("commercial_soft_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_soft_source_v2": _text(
                selected_allatom.get("commercial_soft_source_v2")
            ),
            "allatom_family_focus_commercial_confidence_score_v2": _safe_float(
                selected_allatom.get("commercial_confidence_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_confidence_source_v2": _text(
                selected_allatom.get("commercial_confidence_source_v2")
            ),
            "allatom_family_focus_commercial_overall_score_v2": _safe_float(
                selected_allatom.get("commercial_overall_score_v2"),
                0.0,
            ),
            "allatom_family_focus_commercial_overall_source_v2": _text(
                selected_allatom.get("commercial_overall_source_v2")
            ),
            "allatom_family_focus_commercial_risk_bucket_v2": _text(
                selected_allatom.get("commercial_risk_bucket_v2")
            ),
            "allatom_family_focus_commercial_risk_source_v2": _text(
                selected_allatom.get("commercial_risk_source_v2")
            ),
            "allatom_family_focus_commercial_decision_class_v2": _text(
                selected_allatom.get("commercial_decision_class_v2")
            ),
            "allatom_family_focus_commercial_decision_source_v2": _text(
                selected_allatom.get("commercial_decision_source_v2")
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_v2": list(
                selected_allatom.get("commercial_primary_upgrade_actions_v2", []) or []
            ),
            "allatom_family_focus_commercial_primary_upgrade_actions_text_v2": _text(
                selected_allatom.get("commercial_primary_upgrade_actions_text_v2")
            ),
            "allatom_family_focus_commercial_human_summary_v2": _text(
                selected_allatom.get("commercial_human_summary_v2")
            ),
            "allatom_family_focus_commercial_source_surface_label_v2": _text(
                selected_allatom.get("commercial_source_surface_label_v2")
            ),
            "allatom_family_focus_translation_gate_version": _text(
                selected_allatom.get("translation_gate_version")
            ),
            "allatom_family_focus_translation_gate_focus_status": _text(
                selected_allatom.get("translation_gate_focus_status")
            ),
            "allatom_family_focus_translation_gate_focus_score": _safe_float(
                selected_allatom.get("translation_gate_focus_score"),
                0.0,
            ),
            "allatom_family_focus_translation_gate_focus_reason": _text(
                selected_allatom.get("translation_gate_focus_reason")
            ),
            "allatom_family_focus_stronger_physics_shortlist_version": _text(
                selected_allatom.get("stronger_physics_shortlist_version")
            ),
            "allatom_family_focus_shortlist_tier": _text(selected_allatom.get("focus_shortlist_tier")),
            "allatom_family_focus_recommended_next_expensive_lane": _text(
                selected_allatom.get("recommended_next_expensive_lane")
            ),
            "allatom_family_focus_recommended_next_expensive_lane_reason": _text(
                selected_allatom.get("recommended_next_expensive_lane_reason")
            ),
            "allatom_family_focus_best_compound_name": _text(selected_allatom.get("best_compound_name")),
            "allatom_family_focus_best_compound_name_human_readable": _text(
                selected_allatom.get("best_compound_name_human_readable")
            ),
            "allatom_family_focus_best_compound_name_resolution": _text(
                selected_allatom.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "allatom_family_focus_best_mean_min_distance_A": _safe_float(
                selected_allatom.get("best_mean_min_distance_A"),
                0.0,
            ),
            "allatom_family_focus_promoted_candidate_count": _safe_int(
                selected_allatom.get("promoted_candidate_count"),
                0,
            ),
            "allatom_family_focus_under_2p5_candidate_count": _safe_int(
                selected_allatom.get("under_2p5_candidate_count"),
                0,
            ),
            "allatom_family_focus_near_candidate_count": _safe_int(
                selected_allatom.get("near_candidate_count"),
                0,
            ),
            "selected_allatom_target_id": _text(selected_allatom.get("target_id")),
            "selected_allatom_surface_label": _text(selected_allatom.get("surface_label")),
            "selected_allatom_selected_command_kind": _text(selected_allatom.get("selected_command_kind")),
            "selected_allatom_selected_threshold_A": _safe_float(selected_allatom.get("selected_threshold_A"), 0.0),
            "selected_allatom_packet_scope": _text(selected_allatom.get("packet_scope")),
            "selected_allatom_packet_ready_for_operator_review": bool(
                selected_allatom.get("packet_ready_for_operator_review", False)
            ),
            "selected_allatom_operator_review_ready": bool(
                selected_allatom.get("packet_ready_for_operator_review", False)
            ),
            "selected_allatom_packet_ready_for_operator_review_source": _text(
                selected_allatom.get("packet_ready_for_operator_review_source")
            ),
            "selected_allatom_operator_review_ready_source": _text(
                selected_allatom.get("packet_ready_for_operator_review_source")
            ),
            "selected_allatom_wetlab_gate_pass": bool(selected_allatom.get("wetlab_gate_pass", False)),
            "selected_allatom_wetlab_gate_source": _text(selected_allatom.get("wetlab_gate_source")),
            "selected_allatom_wetlab_final_gate_pass": bool(
                selected_allatom.get("wetlab_final_gate_pass", False)
            ),
            "selected_allatom_wetlab_final_gate_source": _text(
                selected_allatom.get("wetlab_final_gate_source")
            ),
            "selected_allatom_claim_gate_available": bool(
                selected_allatom.get("claim_gate_available", False)
            ),
            "selected_allatom_claim_gate_source": _text(selected_allatom.get("claim_gate_source")),
            "selected_allatom_claim_ready_for_allatom": bool(
                selected_allatom.get("claim_ready_for_allatom", False)
            ),
            "selected_allatom_claim_ready_source": _text(selected_allatom.get("claim_ready_source")),
            "selected_allatom_gate_source_surface_label": _text(
                selected_allatom.get("gate_source_surface_label")
            ),
            "selected_allatom_readiness_semantics": _text(selected_allatom.get("readiness_semantics")),
            "selected_allatom_commercial_reported_v1": bool(
                selected_allatom.get("commercial_reported_v1", False)
            ),
            "selected_allatom_commercial_schema_version": _text(
                selected_allatom.get("commercial_schema_version")
            ),
            "selected_allatom_commercial_hard_gate_pass_v1": bool(
                selected_allatom.get("commercial_hard_gate_pass_v1", False)
            ),
            "selected_allatom_commercial_hard_gate_source_v1": _text(
                selected_allatom.get("commercial_hard_gate_source_v1")
            ),
            "selected_allatom_commercial_overall_score_v1": _safe_float(
                selected_allatom.get("commercial_overall_score_v1"),
                0.0,
            ),
            "selected_allatom_commercial_overall_source_v1": _text(
                selected_allatom.get("commercial_overall_source_v1")
            ),
            "selected_allatom_commercial_risk_bucket_v1": _text(
                selected_allatom.get("commercial_risk_bucket_v1")
            ),
            "selected_allatom_commercial_risk_source_v1": _text(
                selected_allatom.get("commercial_risk_source_v1")
            ),
            "selected_allatom_commercial_decision_class_v1": _text(
                selected_allatom.get("commercial_decision_class_v1")
            ),
            "selected_allatom_commercial_decision_source_v1": _text(
                selected_allatom.get("commercial_decision_source_v1")
            ),
            "selected_allatom_commercial_primary_upgrade_actions_v1": list(
                selected_allatom.get("commercial_primary_upgrade_actions_v1", []) or []
            ),
            "selected_allatom_commercial_primary_upgrade_actions_text_v1": _text(
                selected_allatom.get("commercial_primary_upgrade_actions_text_v1")
            ),
            "selected_allatom_commercial_source_surface_label_v1": _text(
                selected_allatom.get("commercial_source_surface_label_v1")
            ),
            "selected_allatom_commercial_reported_v2": bool(
                selected_allatom.get("commercial_reported_v2", False)
            ),
            "selected_allatom_commercial_schema_version_v2": _text(
                selected_allatom.get("commercial_schema_version_v2")
            ),
            "selected_allatom_commercial_hard_gate_pass_v2": bool(
                selected_allatom.get("commercial_hard_gate_pass_v2", False)
            ),
            "selected_allatom_commercial_hard_gate_source_v2": _text(
                selected_allatom.get("commercial_hard_gate_source_v2")
            ),
            "selected_allatom_commercial_soft_score_v2": _safe_float(
                selected_allatom.get("commercial_soft_score_v2"),
                0.0,
            ),
            "selected_allatom_commercial_soft_source_v2": _text(
                selected_allatom.get("commercial_soft_source_v2")
            ),
            "selected_allatom_commercial_confidence_score_v2": _safe_float(
                selected_allatom.get("commercial_confidence_score_v2"),
                0.0,
            ),
            "selected_allatom_commercial_confidence_source_v2": _text(
                selected_allatom.get("commercial_confidence_source_v2")
            ),
            "selected_allatom_commercial_overall_score_v2": _safe_float(
                selected_allatom.get("commercial_overall_score_v2"),
                0.0,
            ),
            "selected_allatom_commercial_overall_source_v2": _text(
                selected_allatom.get("commercial_overall_source_v2")
            ),
            "selected_allatom_commercial_risk_bucket_v2": _text(
                selected_allatom.get("commercial_risk_bucket_v2")
            ),
            "selected_allatom_commercial_risk_source_v2": _text(
                selected_allatom.get("commercial_risk_source_v2")
            ),
            "selected_allatom_commercial_decision_class_v2": _text(
                selected_allatom.get("commercial_decision_class_v2")
            ),
            "selected_allatom_commercial_decision_source_v2": _text(
                selected_allatom.get("commercial_decision_source_v2")
            ),
            "selected_allatom_commercial_primary_upgrade_actions_v2": list(
                selected_allatom.get("commercial_primary_upgrade_actions_v2", []) or []
            ),
            "selected_allatom_commercial_primary_upgrade_actions_text_v2": _text(
                selected_allatom.get("commercial_primary_upgrade_actions_text_v2")
            ),
            "selected_allatom_commercial_human_summary_v2": _text(
                selected_allatom.get("commercial_human_summary_v2")
            ),
            "selected_allatom_commercial_source_surface_label_v2": _text(
                selected_allatom.get("commercial_source_surface_label_v2")
            ),
            "selected_allatom_translation_gate_version": _text(
                selected_allatom.get("translation_gate_version")
            ),
            "selected_allatom_translation_gate_focus_status": _text(
                selected_allatom.get("translation_gate_focus_status")
            ),
            "selected_allatom_translation_gate_focus_score": _safe_float(
                selected_allatom.get("translation_gate_focus_score"),
                0.0,
            ),
            "selected_allatom_translation_gate_focus_reason": _text(
                selected_allatom.get("translation_gate_focus_reason")
            ),
            "selected_allatom_stronger_physics_shortlist_version": _text(
                selected_allatom.get("stronger_physics_shortlist_version")
            ),
            "selected_allatom_focus_shortlist_tier": _text(selected_allatom.get("focus_shortlist_tier")),
            "selected_allatom_recommended_next_expensive_lane": _text(
                selected_allatom.get("recommended_next_expensive_lane")
            ),
            "selected_allatom_recommended_next_expensive_lane_reason": _text(
                selected_allatom.get("recommended_next_expensive_lane_reason")
            ),
            "selected_allatom_best_compound_name": _text(selected_allatom.get("best_compound_name")),
            "selected_allatom_best_compound_name_human_readable": _text(
                selected_allatom.get("best_compound_name_human_readable")
            ),
            "selected_allatom_best_compound_name_resolution": _text(
                selected_allatom.get("best_compound_name_resolution"),
                default="unresolved",
            ),
            "selected_allatom_best_mean_min_distance_A": _safe_float(
                selected_allatom.get("best_mean_min_distance_A"),
                0.0,
            ),
            "selected_allatom_promoted_candidate_count": _safe_int(
                selected_allatom.get("promoted_candidate_count"),
                0,
            ),
            "selected_allatom_under_2p5_candidate_count": _safe_int(
                selected_allatom.get("under_2p5_candidate_count"),
                0,
            ),
            "selected_allatom_near_candidate_count": _safe_int(
                selected_allatom.get("near_candidate_count"),
                0,
            ),
            "selected_allatom_next_required_step": _text(selected_allatom.get("next_required_step")),
            "selected_rescue_branch_operator_packet_next_required_step": rescue_operator_next_step,
            "selected_rescue_branch_next_required_step": rescue_branch_next_step,
            "selected_manual_retry_target_id": _text(selected_lane_summary.get("target_id")),
            "selected_manual_retry_shard_id": _lane_shard_display(selected_lane_summary),
            "selected_manual_retry_selected_command_kind": _text(selected_lane_summary.get("selected_command_kind")),
            "selected_manual_retry_lane_label": selected_manual_retry_lane_label,
            "selected_manual_retry_ready_for_manual_retry": bool(selected_lane_summary.get("ready_for_manual_retry", False)),
            "current_results_next_required_step": _text(
                selected_krs1_branch_review_next_step,
                dpre1_priority_step,
                rescue_branch_next_step,
                rescue_review_next_step,
                _text(selected_allatom.get("next_required_step")),
                validated_next_step,
                stk17b_followup_review_summary.get("next_required_step") if selected_is_stk17b_followup else "",
                selected_manual_retry_step,
                index_summary.get("next_required_step"),
            ),
            "next_required_step": (
                _text(selected_allatom.get("next_required_step"))
                if _text(selected_allatom.get("next_required_step"))
                else selected_krs1_branch_review_next_step
                if selected_krs1_branch_review_next_step
                else dpre1_priority_step
                if dpre1_priority_step
                else rescue_branch_next_step
                if rescue_branch_next_step
                else rescue_review_next_step
                if rescue_review_next_step
                else validated_next_step
                if validated_next_step
                else _text(stk17b_followup_review_summary.get("next_required_step"))
                if selected_is_stk17b_followup and _text(stk17b_followup_review_summary.get("status")) == "wetlab_stk17b_followup_review_surface_ready"
                else
                selected_manual_retry_step
                if selected_manual_retry_step
                else f"Pause {focus_target_id}; then rerun mapping-fix retries for SARS-CoV-2 Mpro and T. cruzi PDE before reopening auto-start."
                if focus_target_id
                else "Use this summary to choose the next manual retry target."
            ),
        },
        "structured": {
            "hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "retry_preset_artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "current_results_index_artifact": "runs/wetlab_current_results_index_current.md",
            "monitor_semantics_artifact": "runs/wetlab_monitor_semantics_current.md",
            "tcruzi_krs1_branch_review_surface_artifact": "runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
            "dpre1_branch_review_surface_artifact": "runs/wetlab_dpre1_branch_review_surface_current.md",
            "lbdhodh_stage6_tuning_surface_artifact": "runs/wetlab_lbdhodh_stage6_tuning_surface_current.md",
            "lbdhodh_exploratory_retry_lane_artifact": "runs/wetlab_lbdhodh_exploratory_retry_lane_current.md",
            "lbdhodh_gate51_validation_review_surface_artifact": "runs/wetlab_lbdhodh_gate51_validation_review_surface_current.md",
            "tcruzi_pde_rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            "tcruzi_pde_promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "tcruzi_pde_rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "tcruzi_pde_rescue_operator_packet_artifact": "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md",
            "rescue_only_branch_templates_artifact": "runs/wetlab_rescue_only_branch_templates_current.md",
            "tcruzi_pde_allatom_rescue_lane_artifact": "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md",
            "tcruzi_pde_allatom_review_packet_artifact": "runs/wetlab_tcruzi_pde_allatom_review_packet_current.md",
            "cathepsin_k_allatom_refinement_lane_artifact": "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.md",
            "cathepsin_k_allatom_review_packet_artifact": "runs/wetlab_cathepsin_k_allatom_review_packet_current.md",
            "sarscov2_mpro_allatom_refinement_lane_artifact": "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.md",
            "sarscov2_mpro_allatom_review_packet_artifact": "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.md",
            "stk17b_manual_retry_lane_artifact": "runs/wetlab_stk17b_manual_retry_lane_current.md",
            "stk17b_exploratory_retry_lane_artifact": "runs/wetlab_stk17b_exploratory_retry_lane_current.md",
            "stk17b_exploratory_followup_lane_artifact": "runs/wetlab_stk17b_exploratory_followup_lane_current.md",
            "stk17b_followup_review_surface_artifact": "runs/wetlab_stk17b_followup_review_surface_current.md",
            "plpro_manual_retry_lane_artifact": "runs/wetlab_plpro_manual_retry_lane_current.md",
        },
        "rows": manual_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab retry handoff summary.")
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--retry-preset-json", default=DEFAULT_RETRY_PRESET_JSON)
    parser.add_argument("--current-results-index-json", default=DEFAULT_CURRENT_RESULTS_INDEX_JSON)
    parser.add_argument("--monitor-semantics-json", default=DEFAULT_MONITOR_SEMANTICS_JSON)
    parser.add_argument("--dpre1-branch-review-surface-json", default=DEFAULT_DPRE1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-branch-review-surface-json", default=DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--lbdhodh-stage6-tuning-surface-json", default=DEFAULT_LBDHODH_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--lbdhodh-exploratory-retry-lane-json", default=DEFAULT_LBDHODH_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--lbdhodh-gate51-validation-review-surface-json", default=DEFAULT_LBDHODH_GATE51_VALIDATION_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-rescue-review-surface-json", default=DEFAULT_TCRUZI_PDE_RESCUE_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-promoted-top4-review-packet-json", default=DEFAULT_TCRUZI_PDE_PROMOTED_TOP4_REVIEW_PACKET_JSON)
    parser.add_argument("--tcruzi-pde-rescue-only-branch-summary-json", default=DEFAULT_TCRUZI_PDE_RESCUE_ONLY_BRANCH_SUMMARY_JSON)
    parser.add_argument("--tcruzi-pde-rescue-operator-packet-json", default=DEFAULT_TCRUZI_PDE_RESCUE_OPERATOR_PACKET_JSON)
    parser.add_argument("--rescue-only-branch-templates-json", default=DEFAULT_RESCUE_ONLY_BRANCH_TEMPLATES_JSON)
    parser.add_argument("--tcruzi-pde-allatom-rescue-lane-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_RESCUE_LANE_JSON)
    parser.add_argument("--tcruzi-pde-allatom-review-packet-json", default=DEFAULT_TCRUZI_PDE_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--cathepsin-k-allatom-refinement-lane-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_REFINEMENT_LANE_JSON)
    parser.add_argument("--cathepsin-k-allatom-review-packet-json", default=DEFAULT_CATHEPSIN_K_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-refinement-lane-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_REFINEMENT_LANE_JSON)
    parser.add_argument("--sarscov2-mpro-allatom-review-packet-json", default=DEFAULT_SARSCOV2_MPRO_ALLATOM_REVIEW_PACKET_JSON)
    parser.add_argument("--stk17b-manual-retry-lane-json", default=DEFAULT_STK17B_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-retry-lane-json", default=DEFAULT_STK17B_EXPLORATORY_RETRY_LANE_JSON)
    parser.add_argument("--stk17b-exploratory-followup-lane-json", default=DEFAULT_STK17B_EXPLORATORY_FOLLOWUP_LANE_JSON)
    parser.add_argument("--stk17b-followup-review-surface-json", default=DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--plpro-manual-retry-lane-json", default=DEFAULT_PLPRO_MANUAL_RETRY_LANE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.hold_guard_json),
        load_json(args.retry_preset_json),
        load_json(args.current_results_index_json),
        load_json(args.monitor_semantics_json),
        maybe_load_json(args.dpre1_branch_review_surface_json),
        maybe_load_json(args.tcruzi_krs1_branch_review_surface_json),
        maybe_load_json(args.lbdhodh_stage6_tuning_surface_json),
        maybe_load_json(args.lbdhodh_exploratory_retry_lane_json),
        maybe_load_json(args.lbdhodh_gate51_validation_review_surface_json),
        maybe_load_json(args.tcruzi_pde_rescue_review_surface_json),
        maybe_load_json(args.tcruzi_pde_promoted_top4_review_packet_json),
        maybe_load_json(args.tcruzi_pde_rescue_only_branch_summary_json),
        maybe_load_json(args.tcruzi_pde_rescue_operator_packet_json),
        maybe_load_json(args.rescue_only_branch_templates_json),
        maybe_load_json(args.tcruzi_pde_allatom_rescue_lane_json),
        maybe_load_json(args.tcruzi_pde_allatom_review_packet_json),
        maybe_load_json(args.cathepsin_k_allatom_refinement_lane_json),
        maybe_load_json(args.cathepsin_k_allatom_review_packet_json),
        maybe_load_json(args.sarscov2_mpro_allatom_refinement_lane_json),
        maybe_load_json(args.sarscov2_mpro_allatom_review_packet_json),
        maybe_load_json(args.stk17b_manual_retry_lane_json),
        maybe_load_json(args.stk17b_exploratory_retry_lane_json),
        maybe_load_json(args.stk17b_exploratory_followup_lane_json),
        maybe_load_json(args.stk17b_followup_review_surface_json),
        load_json(args.plpro_manual_retry_lane_json),
    )
    write_artifact(args.out_md, "Wet-Lab Retry Handoff Summary", payload)


if __name__ == "__main__":
    main()
