#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_PRIMARY_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_PRIMARY_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_ANTITARGET_QUEUE_JSON = "runs/wetlab_broad_screen_antitarget_execution_queue_current.json"
DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON = "runs/wetlab_stk17b_followup_review_surface_current.json"
DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_krs1_branch_review_surface_current.json"
DEFAULT_TCRUZI_KRS1_GUARDED_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.json"
DEFAULT_OUT_MD = "runs/wetlab_kinase_retry_policy_templates_current.md"

KINASE_TARGETS = (
    {
        "target_id": "STK17B (DRAK2)",
        "template_label": "gate45_branch_only_empirical",
        "command_kind": "throughput_preflight_tuned_gate45",
        "threshold_A": 4.5,
        "default_lane_policy": "keep_default_closed_branch_gate45_only",
        "autostart_policy": "hard_freeze_after_gate45_success",
        "companion_panel_fallback": "open-probe negative control panel",
        "template_scope": "empirical_followup_validated",
    },
    {
        "target_id": "ALK2",
        "template_label": "guarded_tuned_gate55_retry",
        "command_kind": "throughput_preflight_tuned_gate55",
        "threshold_A": 5.5,
        "default_lane_policy": "keep_default_closed_until_tuned_retry_pass",
        "autostart_policy": "guard_stop_after_consecutive_holds",
        "companion_panel_fallback": "ALK2 wild-type comparator",
        "template_scope": "guarded_stage6_failure_template",
    },
    {
        "target_id": "LRRK2",
        "template_label": "panel_first_guarded_tuned_gate55_retry",
        "command_kind": "throughput_preflight_tuned_gate55",
        "threshold_A": 5.5,
        "default_lane_policy": "keep_default_closed_until_primary_full_bulk_ready",
        "autostart_policy": "panel_first_then_guarded_retry_if_failures_emerge",
        "companion_panel_fallback": "kinase selectivity panel",
        "template_scope": "preemptive_panel_first_template",
    },
)


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


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


def _retry_rows_by_target(retry_preset_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for row in retry_preset_payload.get("rows", []) or []:
        candidate = dict(row or {})
        target_id = _text(candidate.get("target_id"))
        if target_id:
            rows[target_id] = candidate
    return rows


def _guard_rows_by_target(hold_guard_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for row in hold_guard_payload.get("rows", []) or []:
        candidate = dict(row or {})
        target_id = _text(candidate.get("target_id"))
        if target_id:
            rows[target_id] = candidate
    return rows


def _first_queue_row_for_target(execution_queue_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    rows = [dict(row or {}) for row in (execution_queue_payload.get("rows", []) or []) if _text((row or {}).get("target_id")) == target_id]
    rows.sort(key=lambda row: _safe_int(row.get("queue_rank"), 0))
    return rows[0] if rows else {}


def _first_unresolved_queue_row_for_target(execution_queue_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    rows = [dict(row or {}) for row in (execution_queue_payload.get("rows", []) or []) if _text((row or {}).get("target_id")) == target_id]
    rows.sort(key=lambda row: _safe_int(row.get("queue_rank"), 0))
    for row in rows:
        status = _text(row.get("queue_status"))
        if status not in {"result_ready", "explicit_hold"}:
            return row
    return rows[-1] if rows else {}


def _first_panel_row_for_target(antitarget_queue_payload: dict[str, Any], target_id: str) -> dict[str, Any]:
    rows = [
        dict(row or {})
        for row in (antitarget_queue_payload.get("rows", []) or [])
        if _text((row or {}).get("primary_target_id")) == target_id
    ]
    rows.sort(key=lambda row: _safe_int(row.get("queue_rank"), 0))
    return rows[0] if rows else {}


def _krs1_gate51_validated(krs1_branch_review_summary: dict[str, Any], krs1_guarded_branch_summary: dict[str, Any]) -> bool:
    branch_state = _text(
        krs1_guarded_branch_summary.get("branch_state"),
        krs1_branch_review_summary.get("branch_state"),
    )
    return bool(
        (
            _text(krs1_guarded_branch_summary.get("status")) == "wetlab_tcruzi_krs1_guarded_branch_summary_validated"
            and bool(krs1_guarded_branch_summary.get("branch_validated", False))
        )
        or (
            _text(krs1_branch_review_summary.get("status")) == "wetlab_tcruzi_krs1_branch_review_surface_ready"
            and bool(krs1_branch_review_summary.get("branch_validated", False))
        )
        or branch_state == "guarded_gate51_validated_default_lane_closed"
    )


def build_payload(
    primary_retry_preset_payload: dict[str, Any] | None,
    primary_hold_guard_payload: dict[str, Any] | None,
    execution_queue_payload: dict[str, Any] | None,
    antitarget_queue_payload: dict[str, Any] | None,
    stk17b_followup_review_surface_payload: dict[str, Any] | None,
    tcruzi_krs1_branch_review_surface_payload: dict[str, Any] | None = None,
    tcruzi_krs1_guarded_branch_summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retry_rows = _retry_rows_by_target(primary_retry_preset_payload or {})
    guard_rows = _guard_rows_by_target(primary_hold_guard_payload or {})
    execution_queue_payload = execution_queue_payload or {}
    antitarget_queue_payload = antitarget_queue_payload or {}
    stk17b_review = _summary(stk17b_followup_review_surface_payload)
    krs1_review = _summary(tcruzi_krs1_branch_review_surface_payload)
    krs1_guarded = _summary(tcruzi_krs1_guarded_branch_summary_payload)

    rows: list[dict[str, Any]] = []
    gate45_only_count = 0
    guarded_gate55_count = 0
    panel_first_count = 0
    empirical_validated_count = 0

    for template in KINASE_TARGETS:
        target_id = template["target_id"]
        retry_row = retry_rows.get(target_id, {})
        guard_row = guard_rows.get(target_id, {})
        unresolved_row = _first_unresolved_queue_row_for_target(execution_queue_payload, target_id)
        queue_row = _first_queue_row_for_target(execution_queue_payload, target_id)
        panel_row = _first_panel_row_for_target(antitarget_queue_payload, target_id)
        selected_command_kind = template["command_kind"]
        selected_threshold_A = float(template["threshold_A"])
        template_label = template["template_label"]
        template_scope = template["template_scope"]
        default_lane_policy = template["default_lane_policy"]
        autostart_policy = template["autostart_policy"]
        companion_panel = _text(
            panel_row.get("anti_target_id"),
            panel_row.get("primary_companion_panel"),
            template.get("companion_panel_fallback"),
        )
        representative_shard_id = _text(
            retry_row.get("representative_stage6_failure_shard_id"),
            retry_row.get("representative_stage1_mapping_failure_shard_id"),
            unresolved_row.get("shard_id"),
            queue_row.get("shard_id"),
        )
        queue_status = _text(unresolved_row.get("queue_status"), queue_row.get("queue_status"))
        recommended_retry_mode = _text(retry_row.get("recommended_retry_mode"))
        next_required_step = _text(retry_row.get("target_specific_next_step"))
        decision = ""
        decision_rationale = ""
        empirical_validated = False

        if target_id == "STK17B (DRAK2)":
            decision = _text(stk17b_review.get("decision"))
            decision_rationale = _text(stk17b_review.get("decision_rationale"))
            next_required_step = _text(stk17b_review.get("next_required_step"), next_required_step)
            selected_threshold_A = _safe_float(stk17b_review.get("exploratory_threshold_A"), selected_threshold_A)
            empirical_validated = bool(stk17b_review.get("branch_to_gate45_only", False))
            if empirical_validated:
                gate45_only_count += 1
                empirical_validated_count += 1
        elif target_id == "ALK2":
            guarded_gate55_count += 1
            if not next_required_step:
                next_required_step = (
                    "Keep ALK2 auto-start closed and reopen only through the tuned gate55 guarded retry path after the neighborhood kinase panel and wild-type comparator are ready."
                )
        else:
            panel_first_count += 1
            recommended_retry_mode = recommended_retry_mode or "panel_first_preemptive_template"
            if not next_required_step:
                next_required_step = (
                    "Keep LRRK2 on the panel-first kinase template; if broad primary failures appear, start with the guarded tuned gate55 retry path instead of reopening the default lane."
                )

        rows.append(
            {
                "row_kind": "kinase_retry_policy_template",
                "target_id": target_id,
                "template_label": template_label,
                "template_scope": template_scope,
                "selected_command_kind": selected_command_kind,
                "selected_threshold_A": selected_threshold_A,
                "default_lane_policy": default_lane_policy,
                "autostart_policy": autostart_policy,
                "companion_panel": companion_panel,
                "representative_shard_id": representative_shard_id,
                "current_queue_status": queue_status,
                "recommended_retry_mode": recommended_retry_mode or template_label,
                "guard_hold_streak": _safe_int(guard_row.get("recent_consecutive_auto_hold_streak")),
                "total_auto_hold_count": _safe_int(guard_row.get("total_auto_hold_count")),
                "empirical_validated": empirical_validated,
                "decision": decision or template_label,
                "decision_rationale": decision_rationale,
                "evidence_source": (
                    "runs/wetlab_stk17b_followup_review_surface_current.md"
                    if target_id == "STK17B (DRAK2)"
                    else "runs/wetlab_primary_retry_preset_surface_current.md"
                    if retry_row
                    else "runs/wetlab_broad_screen_antitarget_execution_queue_current.md"
                ),
                "next_required_step": next_required_step,
            }
        )

    if _krs1_gate51_validated(krs1_review, krs1_guarded):
        empirical_validated_count += 1
        rows.append(
            {
                "row_kind": "kinase_retry_policy_template",
                "target_id": _text(krs1_guarded.get("target_id"), krs1_review.get("target_id"), default="T. cruzi KRS1"),
                "template_label": "gate51_branch_only_empirical",
                "template_scope": "empirical_validation_promoted",
                "selected_command_kind": _text(
                    krs1_guarded.get("selected_command_kind"),
                    krs1_review.get("exploratory_retry_selected_command_kind"),
                    default="throughput_preflight_tuned_gate51",
                ),
                "selected_threshold_A": _safe_float(
                    krs1_guarded.get("selected_threshold_A"),
                    _safe_float(krs1_review.get("exploratory_retry_selected_threshold_A"), 5.1),
                ),
                "default_lane_policy": "keep_default_closed_branch_gate51_only",
                "autostart_policy": "manual_review_before_any_reopen",
                "companion_panel": _text(krs1_review.get("successor_target"), default="LRRK2 successor broad lane"),
                "representative_shard_id": _text(
                    krs1_guarded.get("validated_end_shard_id"),
                    krs1_guarded.get("validated_start_shard_id"),
                    krs1_review.get("shard_id"),
                ),
                "current_queue_status": "validated_branch_only",
                "recommended_retry_mode": "gate51_validated_branch_only",
                "guard_hold_streak": 0,
                "total_auto_hold_count": 0,
                "empirical_validated": True,
                "decision": "promote_gate51_validated_keep_default_closed",
                "decision_rationale": _text(
                    krs1_guarded.get("next_required_step"),
                    krs1_review.get("next_required_step"),
                ),
                "evidence_source": "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md",
                "next_required_step": _text(krs1_guarded.get("next_required_step"), krs1_review.get("next_required_step")),
            }
        )

    if not gate45_only_count:
        gate45_only_count = sum(1 for row in rows if str(row.get("template_label", "")).strip().startswith("gate45"))
    if not guarded_gate55_count:
        guarded_gate55_count = sum(1 for row in rows if "gate55" in str(row.get("selected_command_kind", "")))
    if not panel_first_count:
        panel_first_count = sum(1 for row in rows if "panel_first" in str(row.get("template_label", "")))

    focus_row = next(
        (
            row
            for row in rows
            if _text(row.get("target_id")) == "T. cruzi KRS1"
            and _text(row.get("template_label")) == "gate51_branch_only_empirical"
            and bool(row.get("empirical_validated", False))
        ),
        next((row for row in rows if _text(row.get("target_id")) == "STK17B (DRAK2)"), rows[0] if rows else {}),
    )
    next_required_step = _text(
        focus_row.get("next_required_step"),
        "Keep STK17B on the gate4.5 branch-only kinase template, keep ALK2 on the guarded gate55 template, and treat LRRK2 as panel-first until broad failure evidence appears.",
    )
    return {
        "summary": {
            "status": "wetlab_kinase_retry_policy_templates_ready",
            "template_target_count": len(rows),
            "empirical_validated_target_count": empirical_validated_count,
            "gate45_only_target_count": gate45_only_count,
            "guarded_gate55_candidate_target_count": guarded_gate55_count,
            "panel_first_template_target_count": panel_first_count,
            "focus_target_id": _text(focus_row.get("target_id")),
            "focus_template_label": _text(focus_row.get("template_label")),
            "focus_selected_command_kind": _text(focus_row.get("selected_command_kind")),
            "focus_selected_threshold_A": _safe_float(focus_row.get("selected_threshold_A"), 0.0),
            "next_required_step": next_required_step,
        },
        "structured": {
            "primary_retry_preset_artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "primary_hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "stk17b_followup_review_surface_artifact": "runs/wetlab_stk17b_followup_review_surface_current.md",
            "tcruzi_krs1_branch_review_surface_artifact": "runs/wetlab_tcruzi_krs1_branch_review_surface_current.md",
            "tcruzi_krs1_guarded_branch_summary_artifact": "runs/wetlab_tcruzi_krs1_guarded_branch_summary_current.md",
            "antitarget_execution_queue_artifact": "runs/wetlab_broad_screen_antitarget_execution_queue_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reusable kinase retry policy templates from empirical and guarded broad-screen outcomes.")
    parser.add_argument("--primary-retry-preset-json", default=DEFAULT_PRIMARY_RETRY_PRESET_JSON)
    parser.add_argument("--primary-hold-guard-json", default=DEFAULT_PRIMARY_HOLD_GUARD_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--antitarget-queue-json", default=DEFAULT_ANTITARGET_QUEUE_JSON)
    parser.add_argument("--stk17b-followup-review-surface-json", default=DEFAULT_STK17B_FOLLOWUP_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-branch-review-surface-json", default=DEFAULT_TCRUZI_KRS1_BRANCH_REVIEW_SURFACE_JSON)
    parser.add_argument("--tcruzi-krs1-guarded-branch-summary-json", default=DEFAULT_TCRUZI_KRS1_GUARDED_BRANCH_SUMMARY_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Kinase Retry Policy Templates",
        build_payload(
            load_json(args.primary_retry_preset_json),
            load_json(args.primary_hold_guard_json),
            load_json(args.execution_queue_json),
            load_json(args.antitarget_queue_json),
            maybe_load_json(args.stk17b_followup_review_surface_json),
            maybe_load_json(args.tcruzi_krs1_branch_review_surface_json),
            maybe_load_json(args.tcruzi_krs1_guarded_branch_summary_json),
        ),
    )


if __name__ == "__main__":
    main()
