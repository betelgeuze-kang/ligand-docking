#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

DEFAULT_STAGE1_MAPPING_FIX_LANES_JSON = "runs/wetlab_stage1_mapping_fix_lanes_current.json"
DEFAULT_SARSCOV2_MPRO_STAGE1_MAPPING_FIX_LANE_JSON = "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.json"
DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON = "runs/tcruzi_pde_stage1_mapping_fix_lane_current.json"
DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.json"
DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_tcruzi_pde_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_mapping_fix_retry_policy_templates_current.md"


TARGET_CLASS_BY_TARGET_ID = {
    "SARS-CoV-2 Mpro": "viral_protease",
    "T. cruzi PDE": "pathogen_phosphodiesterase",
}


TARGET_SCOPE_BY_TARGET_ID = {
    "SARS-CoV-2 Mpro": "viral_stage1_mapping_repair_template",
    "T. cruzi PDE": "pathogen_stage1_mapping_repair_template",
}


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


def _lane_row(target_id: str, lane_payload: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(lane_payload)
    return {
        "row_kind": "target_retry_policy_template",
        "target_id": target_id,
        "template_label": "mapping_fix_branch_only",
        "template_scope": TARGET_SCOPE_BY_TARGET_ID.get(target_id, "stage1_mapping_repair_template"),
        "target_class": TARGET_CLASS_BY_TARGET_ID.get(target_id, "mapping_fragile_target"),
        "selected_command_kind": _text(summary.get("selected_command_kind"), default="throughput_preflight"),
        "selected_threshold_A": 0.0,
        "default_lane_policy": "keep_default_closed_until_mapping_fix_clean_summary",
        "autostart_policy": "manual_mapping_diagnostics_before_any_reopen",
        "companion_panel": "mapping diagnostics rerun lane",
        "recommended_retry_mode": _text(summary.get("recommended_retry_mode"), default="mapping_fix_required"),
        "empirical_validated": False,
        "ready_for_retry": bool(summary.get("ready_for_mapping_fix_retry", False)),
        "stage1_mapping_failed_count": _safe_int(summary.get("stage1_mapping_failed_count")),
        "stage6_distance_gate_failed_count": _safe_int(summary.get("stage6_distance_gate_failed_count")),
        "guard_limit": _safe_int(summary.get("guard_limit")),
        "decision": "branch_to_mapping_fix_only_keep_default_closed",
        "decision_rationale": "Stage1 ligand mapping must be repaired and revalidated before any default-lane reopen is allowed.",
        "evidence_source": _text(summary.get("lane_artifact"), default=""),
        "shard_id": _text(summary.get("shard_id")),
        "next_required_step": _text(summary.get("next_required_step")),
    }


def _stage6_tuning_ready(payload: dict[str, Any] | None, target_id: str) -> bool:
    summary = _summary(payload)
    status = _text(summary.get("status"))
    return bool(status.endswith("stage6_tuning_surface_ready") and _text(summary.get("target_id")) == target_id)


def build_payload(
    stage1_mapping_fix_lanes: dict[str, Any] | None,
    sarscov2_mpro_stage1_mapping_fix_lane: dict[str, Any] | None = None,
    tcruzi_pde_stage1_mapping_fix_lane: dict[str, Any] | None = None,
    sarscov2_mpro_stage6_tuning_surface: dict[str, Any] | None = None,
    tcruzi_pde_stage6_tuning_surface: dict[str, Any] | None = None,
) -> dict[str, Any]:
    support_summary = _summary(stage1_mapping_fix_lanes)
    lane_payloads = [
        ("SARS-CoV-2 Mpro", sarscov2_mpro_stage1_mapping_fix_lane or {}),
        ("T. cruzi PDE", tcruzi_pde_stage1_mapping_fix_lane or {}),
    ]

    rows: list[dict[str, Any]] = []
    ready_targets: list[str] = []
    for target_id, payload in lane_payloads:
        if target_id == "SARS-CoV-2 Mpro" and _stage6_tuning_ready(sarscov2_mpro_stage6_tuning_surface, target_id):
            continue
        if target_id == "T. cruzi PDE" and _stage6_tuning_ready(tcruzi_pde_stage6_tuning_surface, target_id):
            continue
        summary = _summary(payload)
        if _text(summary.get("status")) != "wetlab_mapping_fix_retry_lane_ready":
            continue
        row = _lane_row(target_id, payload)
        rows.append(row)
        if bool(row.get("ready_for_retry", False)):
            ready_targets.append(target_id)

    focus_row = rows[0] if rows else {}
    next_required_step = _text(
        support_summary.get("next_required_step"),
        focus_row.get("next_required_step"),
        default="Run the mapping-fix retry runner for the first ready target and keep default auto-start blocked until a clean mapping summary lands.",
    )

    return {
        "summary": {
            "status": "wetlab_mapping_fix_retry_policy_templates_ready",
            "template_target_count": len(rows),
            "ready_target_count": len(ready_targets),
            "ready_targets": "; ".join(ready_targets),
            "focus_target_id": _text(focus_row.get("target_id")),
            "focus_template_label": _text(focus_row.get("template_label"), default="mapping_fix_branch_only"),
            "focus_selected_command_kind": _text(focus_row.get("selected_command_kind"), default="throughput_preflight"),
            "next_required_step": next_required_step,
        },
        "structured": {
            "stage1_mapping_fix_lanes_artifact": "runs/wetlab_stage1_mapping_fix_lanes_current.md",
            "sarscov2_mpro_stage1_mapping_fix_lane_artifact": "runs/sarscov2_mpro_stage1_mapping_fix_lane_current.md",
            "tcruzi_pde_stage1_mapping_fix_lane_artifact": "runs/tcruzi_pde_stage1_mapping_fix_lane_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mapping-fix retry policy templates for stage1-repair targets.")
    parser.add_argument("--stage1-mapping-fix-lanes-json", default=DEFAULT_STAGE1_MAPPING_FIX_LANES_JSON)
    parser.add_argument("--sarscov2-mpro-stage1-mapping-fix-lane-json", default=DEFAULT_SARSCOV2_MPRO_STAGE1_MAPPING_FIX_LANE_JSON)
    parser.add_argument("--tcruzi-pde-stage1-mapping-fix-lane-json", default=DEFAULT_TCRUZI_PDE_STAGE1_MAPPING_FIX_LANE_JSON)
    parser.add_argument("--sarscov2-mpro-stage6-tuning-surface-json", default=DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-stage6-tuning-surface-json", default=DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(
        args.out_md,
        "Wet-Lab Mapping-Fix Retry Policy Templates",
        build_payload(
            load_json(args.stage1_mapping_fix_lanes_json),
            maybe_load_json(args.sarscov2_mpro_stage1_mapping_fix_lane_json),
            maybe_load_json(args.tcruzi_pde_stage1_mapping_fix_lane_json),
            maybe_load_json(args.sarscov2_mpro_stage6_tuning_surface_json),
            maybe_load_json(args.tcruzi_pde_stage6_tuning_surface_json),
        ),
    )


if __name__ == "__main__":
    main()
