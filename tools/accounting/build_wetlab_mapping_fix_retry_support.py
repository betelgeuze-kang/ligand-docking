#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools import build_wetlab_mapping_fix_retry_lane as lane_mod
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RETRY_PRESET_JSON = "runs/wetlab_primary_retry_preset_surface_current.json"
DEFAULT_EXECUTION_QUEUE_JSON = "runs/wetlab_broad_screen_execution_queue_current.json"
DEFAULT_COMPOUND_UNIVERSE_JSON = "runs/wetlab_broad_screen_compound_universe_current.json"
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_TARGET_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_sarscov2_mpro_stage6_tuning_surface_current.json"
DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON = "runs/wetlab_tcruzi_pde_stage6_tuning_surface_current.json"
DEFAULT_OUT_MD = "runs/wetlab_mapping_fix_retry_support_current.md"
TARGETS = (
    ("SARS-CoV-2 Mpro", "runs/sarscov2_mpro_mapping_fix_retry_lane_current.md"),
    ("T. cruzi PDE", "runs/tcruzi_pde_mapping_fix_retry_lane_current.md"),
)


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(value: Any) -> str:
    return str(value or "").strip()


def _stage6_tuning_ready(payload: dict[str, Any] | None, target_id: str) -> bool:
    summary = _summary(payload)
    return _text(summary.get("status")).endswith("stage6_tuning_surface_ready") and _text(summary.get("target_id")) == target_id


def build_payload(
    *,
    retry_preset_payload: dict[str, Any],
    execution_queue_payload: dict[str, Any],
    compound_universe_payload: dict[str, Any],
    portfolio_payload: dict[str, Any],
    target_native_csv: str,
    sarscov2_mpro_stage6_tuning_surface: dict[str, Any] | None = None,
    tcruzi_pde_stage6_tuning_surface: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[tuple[str, str, dict[str, Any]]]]:
    lane_outputs: list[tuple[str, str, dict[str, Any]]] = []
    rows: list[dict[str, Any]] = []
    ready_targets: list[str] = []
    focus_next_step = ""

    for target_id, out_md in TARGETS:
        if target_id == "SARS-CoV-2 Mpro" and _stage6_tuning_ready(sarscov2_mpro_stage6_tuning_surface, target_id):
            continue
        if target_id == "T. cruzi PDE" and _stage6_tuning_ready(tcruzi_pde_stage6_tuning_surface, target_id):
            continue
        payload = lane_mod.build_payload(
            retry_preset_payload=retry_preset_payload,
            execution_queue_payload=execution_queue_payload,
            compound_universe_payload=compound_universe_payload,
            portfolio_payload=portfolio_payload,
            target_native_csv=target_native_csv,
            target_id=target_id,
            lane_artifact_md=out_md,
        )
        lane_outputs.append((target_id, out_md, payload))
        summary = _summary(payload)
        rows_by_kind = {str(row.get("row_kind", "")).strip(): dict(row) for row in (payload.get("rows", []) or [])}
        runner_row = rows_by_kind.get("runner_command", {})
        diagnostics_row = rows_by_kind.get("selected_bridge_command", {})
        row = {
            "target_id": target_id,
            "lane_artifact": out_md,
            "shard_id": _text(summary.get("shard_id")),
            "recommended_retry_mode": _text(summary.get("recommended_retry_mode")),
            "stage1_mapping_failed_count": int(summary.get("stage1_mapping_failed_count", 0) or 0),
            "stage6_distance_gate_failed_count": int(summary.get("stage6_distance_gate_failed_count", 0) or 0),
            "selected_command_kind": _text(summary.get("selected_command_kind")),
            "ready_for_mapping_fix_retry": bool(summary.get("ready_for_mapping_fix_retry", False)),
            "diagnostics_command_kind": _text(diagnostics_row.get("command_kind")),
            "diagnostics_command": _text(diagnostics_row.get("command")),
            "runner_command": _text(runner_row.get("command")),
            "one_line_summary": _text(summary.get("next_required_step")),
        }
        rows.append(row)
        if row["ready_for_mapping_fix_retry"]:
            ready_targets.append(target_id)
            if not focus_next_step:
                focus_next_step = row["one_line_summary"]

    payload = {
        "summary": {
            "status": "wetlab_mapping_fix_retry_support_ready",
            "target_count": len(TARGETS),
            "ready_target_count": len(ready_targets),
            "ready_targets": "; ".join(ready_targets),
            "mapping_fix_candidate_count": sum(1 for row in rows if row["recommended_retry_mode"] == "mapping_fix_required"),
            "next_required_step": focus_next_step or "Review the mapping-fix retry lanes before reopening auto-start.",
        },
        "structured": {
            "retry_preset_artifact": "runs/wetlab_primary_retry_preset_surface_current.md",
            "support_targets": [out_md for _, out_md, _ in lane_outputs],
        },
        "rows": rows,
    }
    return payload, lane_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build target-specific mapping-fix retry support for SARS-CoV-2 Mpro and T. cruzi PDE.")
    parser.add_argument("--retry-preset-json", default=DEFAULT_RETRY_PRESET_JSON)
    parser.add_argument("--execution-queue-json", default=DEFAULT_EXECUTION_QUEUE_JSON)
    parser.add_argument("--compound-universe-json", default=DEFAULT_COMPOUND_UNIVERSE_JSON)
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--target-native-csv", default=DEFAULT_TARGET_NATIVE_CSV)
    parser.add_argument("--sarscov2-mpro-stage6-tuning-surface-json", default=DEFAULT_SARSCOV2_MPRO_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--tcruzi-pde-stage6-tuning-surface-json", default=DEFAULT_TCRUZI_PDE_STAGE6_TUNING_SURFACE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload, lane_outputs = build_payload(
        retry_preset_payload=load_json(args.retry_preset_json),
        execution_queue_payload=load_json(args.execution_queue_json),
        compound_universe_payload=load_json(args.compound_universe_json),
        portfolio_payload=load_json(args.portfolio_json),
        target_native_csv=args.target_native_csv,
        sarscov2_mpro_stage6_tuning_surface=load_json(args.sarscov2_mpro_stage6_tuning_surface_json),
        tcruzi_pde_stage6_tuning_surface=load_json(args.tcruzi_pde_stage6_tuning_surface_json),
    )
    for target_id, out_md, lane_payload in lane_outputs:
        write_artifact(out_md, f"{target_id} Mapping-Fix Retry Lane", lane_payload)
    write_artifact(args.out_md, "Wet-Lab Mapping-Fix Retry Support", payload)


if __name__ == "__main__":
    main()
