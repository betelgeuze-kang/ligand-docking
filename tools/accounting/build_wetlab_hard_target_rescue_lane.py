#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_STAGE6_FAILURE_SURFACE_JSON = "runs/wetlab_primary_stage6_failure_surface_current.json"
DEFAULT_HOLD_GUARD_JSON = "runs/wetlab_primary_hold_guard_surface_current.json"
DEFAULT_RETRY_POLICY_TEMPLATES_JSON = "runs/wetlab_target_retry_policy_templates_current.json"
DEFAULT_OUT_MD = "runs/wetlab_hard_target_rescue_lane_current.md"
DEFAULT_MIN_AUTO_HOLD_STREAK = 3
DEFAULT_TOP_N_THREE_BEAD = 32


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ""}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {None, ""}:
            return default
        return int(value)
    except Exception:
        return default


def _stage1_ok(summary_payload: dict[str, Any], detail_row: dict[str, Any]) -> tuple[bool, str]:
    stage1 = dict((summary_payload.get("stages", {}) or {}).get("stage1_ligand_mapping", {}) or {})
    raw = stage1.get("pass", stage1.get("ok", detail_row.get("stage1_mapping_pass")))
    if raw is True:
        return True, "stage1_ligand_mapping.pass"
    if raw is False:
        return False, "stage1_ligand_mapping.pass"
    failed_stage = _text(detail_row.get("failed_stage")) or _text((summary_payload.get("service_result", {}) or {}).get("failed_stage"))
    if failed_stage == "stage6_operational_gate":
        return True, "inferred_from_stage6_fail"
    return False, ""


def _preset_mismatch(summary_payload: dict[str, Any]) -> dict[str, Any]:
    traj_prod = dict(summary_payload.get("traj_prod", {}) or {})
    if not traj_prod:
        stage2 = dict((summary_payload.get("stages", {}) or {}).get("stage2_trajectory_generation", {}) or {})
        traj_prod = dict(stage2.get("traj_prod", {}) or {})
        if not traj_prod:
            traj_prod = dict(stage2.get("traj_stage2_preset_diagnostics", {}) or {})
    requested = _text(traj_prod.get("requested_preset") or traj_prod.get("requested"))
    resolved = _text(traj_prod.get("resolved_preset") or traj_prod.get("resolved"))
    hinted = [str(value).strip() for value in (traj_prod.get("hinted_families") or []) if str(value).strip()]
    warnings = [str(value).strip() for value in (traj_prod.get("warnings") or []) if str(value).strip()]
    effective = resolved or requested
    mismatch = bool(effective and hinted and effective not in hinted)
    return {
        "mismatch": mismatch,
        "requested_preset": requested,
        "resolved_preset": resolved,
        "hinted_families": hinted,
        "warnings": warnings,
    }


def _priority_key(row: dict[str, Any]) -> tuple[int, float, int, str]:
    ready = 0 if bool(row.get("ready_for_manual_retry", False)) else 1
    three_bead = 0 if bool(row.get("top_n_three_bead_recommended", False)) else 1
    observed = -_safe_float(row.get("mean_min_distance_A"))
    return (ready, three_bead, observed, _text(row.get("target_id")))


def _stage2_preset_override(mismatch: dict[str, Any], retry_row: dict[str, Any]) -> str:
    hinted = [_text(value) for value in mismatch.get("hinted_families", []) or [] if _text(value)]
    if hinted:
        return hinted[0]
    resolved = _text(mismatch.get("resolved_preset"))
    requested = _text(mismatch.get("requested_preset"))
    template_label = _text(retry_row.get("template_label"))
    return resolved or requested or template_label


def _target_retry_template_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows", []) or []:
        target_id = _text((row or {}).get("target_id"))
        if target_id:
            rows[target_id] = dict(row)
    return rows


def _guard_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows", []) or []:
        target_id = _text((row or {}).get("target_id"))
        if target_id:
            rows[target_id] = dict(row)
    return rows


def build_payload(
    execution_queue_payload: dict[str, Any],
    stage6_failure_surface_payload: dict[str, Any],
    hold_guard_payload: dict[str, Any],
    retry_policy_templates_payload: dict[str, Any],
    *,
    min_auto_hold_streak: int = DEFAULT_MIN_AUTO_HOLD_STREAK,
    top_n_three_bead: int = DEFAULT_TOP_N_THREE_BEAD,
) -> dict[str, Any]:
    guard_rows = _guard_rows(hold_guard_payload)
    retry_rows = _target_retry_template_rows(retry_policy_templates_payload)
    grouped_candidates: dict[str, list[dict[str, Any]]] = {}

    for detail_row in stage6_failure_surface_payload.get("rows", []) or []:
        row = dict(detail_row or {})
        target_id = _text(row.get("target_id"))
        shard_id = _text(row.get("shard_id"))
        failed_stage = _text(row.get("failed_stage"))
        if not target_id or not shard_id or failed_stage != "stage6_operational_gate":
            continue
        guard_row = guard_rows.get(target_id, {})
        auto_hold_streak = max(
            _safe_int(guard_row.get("recent_consecutive_auto_hold_streak")),
            _safe_int(guard_row.get("total_auto_hold_count")),
        )
        if auto_hold_streak < int(min_auto_hold_streak):
            continue
        summary_json = _text(row.get("summary_json"))
        summary_payload = maybe_load_json(summary_json)
        stage1_ok, stage1_source = _stage1_ok(summary_payload, row)
        if not stage1_ok:
            continue
        mismatch = _preset_mismatch(summary_payload)
        retry_row = retry_rows.get(target_id, {})
        base_command_kind = _text(retry_row.get("selected_command_kind")) or "throughput_preflight"
        stage2_preset_override = _stage2_preset_override(mismatch, retry_row)
        mean_min_distance = _safe_float(row.get("mean_min_distance_A"))
        queue_rows_for_target = [
            dict(queue_row)
            for queue_row in (execution_queue_payload.get("rows", []) or [])
            if _text(queue_row.get("target_id")) == target_id
        ]
        fully_resolved = bool(queue_rows_for_target) and all(
            _text(queue_row.get("queue_status")) in {"explicit_hold", "result_ready"} for queue_row in queue_rows_for_target
        )
        next_required = (
            f"Resolve the preset mismatch guard for {target_id} first; then rerun shard {shard_id} through the hard-target rescue lane."
            if mismatch.get("mismatch", False)
            else f"Run the hard-target rescue lane for {target_id} {shard_id} with slow local refinement and rescue-only anchors."
        )
        grouped_candidates.setdefault(target_id, []).append(
            {
                "row_kind": "hard_target_rescue_candidate",
                "target_id": target_id,
                "target_slug": slug(target_id),
                "shard_id": shard_id,
                "summary_json": summary_json,
                "stage1_ok": True,
                "stage1_ok_source": stage1_source,
                "stage6_fail": True,
                "mean_min_distance_A": mean_min_distance,
                "distance_over_threshold_A": _safe_float(row.get("distance_over_threshold_A")),
                "auto_hold_streak_count": auto_hold_streak,
                "rescue_eligibility_rule": f"stage1_ok && stage6_fail && auto_hold_streak >= {int(min_auto_hold_streak)}",
                "preset_mismatch_hard_guard_active": bool(mismatch.get("mismatch", False)),
                "preset_mismatch_requested_preset": _text(mismatch.get("requested_preset")),
                "preset_mismatch_resolved_preset": _text(mismatch.get("resolved_preset")),
                "preset_mismatch_hinted_families": "; ".join(mismatch.get("hinted_families", [])),
                "rescue_command_kind": "throughput_preflight_hard_target_rescue",
                "rescue_base_command_kind": base_command_kind,
                "rescue_profile_label": "slow_local_refine_stage6_rescue_v1",
                "rescue_gate_threshold_A": 2.5,
                "rescue_reads_anchor_artifacts_only": True,
                "selected_command_kind": "throughput_preflight_hard_target_rescue",
                "stage2_preset_override": stage2_preset_override,
                "anchor_artifact_required": True,
                "three_bead_recommended": mean_min_distance >= 5.0,
                "top_n_three_bead_recommended": mean_min_distance >= 5.0,
                "top_n_three_bead_count": int(top_n_three_bead) if mean_min_distance >= 5.0 else 0,
                "ready_for_manual_retry": not bool(mismatch.get("mismatch", False)),
                "default_lane_policy": "keep_default_closed",
                "queue_fully_resolved": fully_resolved,
                "next_required_step": next_required,
            }
        )

    candidates: list[dict[str, Any]] = []
    for target_id, rows in grouped_candidates.items():
        rows.sort(
            key=lambda row: (
                _safe_int(_text(row.get("shard_id")).split("_of_", 1)[0], 0),
                _safe_float(row.get("mean_min_distance_A")),
            )
        )
        selected = dict(rows[-1])
        selected["rescue_candidate_shard_count"] = len(rows)
        selected["rescue_candidate_shard_ids"] = ";".join(_text(row.get("shard_id")) for row in rows)
        candidates.append(selected)

    candidates.sort(key=_priority_key)
    focus = candidates[0] if candidates else {}
    ready_count = sum(1 for row in candidates if bool(row.get("ready_for_manual_retry", False)))
    blocked_count = sum(1 for row in candidates if not bool(row.get("ready_for_manual_retry", False)))
    return {
        "summary": {
            "status": "wetlab_hard_target_rescue_lane_ready",
            "candidate_target_count": len({_text(row.get('target_id')) for row in candidates if _text(row.get('target_id'))}),
            "candidate_row_count": len(candidates),
            "ready_target_count": ready_count,
            "blocked_by_preset_mismatch_target_count": blocked_count,
            "rescue_min_auto_hold_streak": int(min_auto_hold_streak),
            "rescue_top_n_three_bead_default": int(top_n_three_bead),
            "focus_target_id": _text(focus.get("target_id")),
            "focus_shard_id": _text(focus.get("shard_id")),
            "focus_ready_for_manual_retry": bool(focus.get("ready_for_manual_retry", False)),
            "focus_stage1_ok": bool(focus.get("stage1_ok", False)),
            "focus_stage6_fail": bool(focus.get("stage6_fail", False)),
            "focus_rescue_base_command_kind": _text(focus.get("rescue_base_command_kind")),
            "focus_rescue_command_kind": _text(focus.get("rescue_command_kind")),
            "focus_stage2_preset_override": _text(focus.get("stage2_preset_override")),
            "focus_top_n_three_bead_recommended": bool(focus.get("top_n_three_bead_recommended", False)),
            "focus_auto_hold_streak": _safe_int(focus.get("auto_hold_streak_count")),
            "focus_lane_label": "hard_target_rescue",
            "focus_next_required_step": _text(focus.get("next_required_step")) or "No hard-target rescue candidate is currently ready.",
            "target_id": _text(focus.get("target_id")),
            "shard_id": _text(focus.get("shard_id")),
            "ready_for_manual_retry": bool(focus.get("ready_for_manual_retry", False)),
            "stage1_ok": bool(focus.get("stage1_ok", False)),
            "stage6_fail": bool(focus.get("stage6_fail", False)),
            "auto_hold_streak": _safe_int(focus.get("auto_hold_streak_count")),
            "selected_command_kind": _text(focus.get("selected_command_kind") or focus.get("rescue_command_kind")),
            "rescue_base_command_kind": _text(focus.get("rescue_base_command_kind")),
            "lane_label": "hard_target_rescue",
            "stage2_preset_override": _text(focus.get("stage2_preset_override")),
            "top_n_three_bead_recommended": bool(focus.get("top_n_three_bead_recommended", False)),
            "preset_mismatch_hard_guard_active": bool(focus.get("preset_mismatch_hard_guard_active", False)),
            "next_required_step": _text(focus.get("next_required_step")) or "No hard-target rescue candidate is currently ready.",
        },
        "structured": {
            "execution_queue_artifact": "runs/wetlab_broad_screen_execution_queue_current.md",
            "stage6_failure_surface_artifact": "runs/wetlab_primary_stage6_failure_surface_current.md",
            "hold_guard_artifact": "runs/wetlab_primary_hold_guard_surface_current.md",
            "retry_policy_templates_artifact": "runs/wetlab_target_retry_policy_templates_current.md",
        },
        "rows": candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a hard-target rescue lane for stage1-pass/stage6-fail broad-screen shards.")
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--stage6-failure-surface-json", default=DEFAULT_STAGE6_FAILURE_SURFACE_JSON)
    parser.add_argument("--hold-guard-json", default=DEFAULT_HOLD_GUARD_JSON)
    parser.add_argument("--retry-policy-templates-json", default=DEFAULT_RETRY_POLICY_TEMPLATES_JSON)
    parser.add_argument("--min-auto-hold-streak", type=int, default=DEFAULT_MIN_AUTO_HOLD_STREAK)
    parser.add_argument("--top-n-three-bead", type=int, default=DEFAULT_TOP_N_THREE_BEAD)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.execution_queue_json),
        load_json(args.stage6_failure_surface_json),
        load_json(args.hold_guard_json),
        load_json(args.retry_policy_templates_json),
        min_auto_hold_streak=max(1, int(args.min_auto_hold_streak)),
        top_n_three_bead=max(1, int(args.top_n_three_bead)),
    )
    write_artifact(args.out_md, "Wet-Lab Hard Target Rescue Lane", payload)


if __name__ == "__main__":
    main()
