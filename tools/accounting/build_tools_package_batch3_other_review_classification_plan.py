#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH3_PLAN_JSON = "runs/tools_package_batch3_review_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch3_other_review_classification_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch3_other_review_classification_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch3_other_review_classification_plan_current.md"

BATCH3_MANUAL_PACKAGE_DECISIONS: dict[str, tuple[str, str]] = {
    "ab_test_ai_hip_graph": ("product", "product_rocm_ai_runtime_ab"),
    "benchmark_idp_force_components": ("product", "idp_product_scope_force_benchmark"),
    "benchmark_idp_hbond_prepare_components": ("product", "idp_product_scope_hbond_benchmark"),
    "build_alk2_launch_packet": ("wetlab", "wetlab_alk2_campaign"),
    "build_alk2_live_progress": ("wetlab", "wetlab_alk2_campaign"),
    "build_alk2_render_suite": ("wetlab", "wetlab_alk2_campaign"),
    "build_alk2_result_summary": ("wetlab", "wetlab_alk2_campaign"),
    "build_alk2_run_record": ("wetlab", "wetlab_alk2_campaign"),
    "build_blind_validation_bundle": ("product", "product_blind_validation"),
    "build_blind_validation_summary": ("product", "product_blind_validation"),
    "build_caix_broad_screen_shard_04_result_rows": ("wetlab", "wetlab_caix_campaign"),
    "build_caix_slow_shard_preset": ("wetlab", "wetlab_caix_campaign"),
    "build_caix_stage6_gate_tuning_surface": ("wetlab", "wetlab_caix_campaign"),
    "build_cathepsin_k_live_progress": ("wetlab", "wetlab_cathepsin_k_campaign"),
    "build_cathepsin_k_result_summary": ("wetlab", "wetlab_cathepsin_k_campaign"),
    "build_competition_external_operator_track": ("product", "product_competition_operator_track"),
    "build_docking_ranking_mutation_e2e_smoke": ("product", "product_docking_ranking_smoke"),
    "build_external_validation_submission_sets": ("product", "product_external_validation"),
    "build_idp_3bead_benchmark_matrix": ("product", "idp_product_scope_benchmark"),
    "build_idp_3bead_strict_benchmark": ("product", "idp_product_scope_benchmark"),
    "build_idp_branch_feature_report": ("product", "idp_product_scope_feature_report"),
    "build_idp_global_aggregation_dashboard": ("product", "idp_product_scope_dashboard"),
    "build_idp_release_report": ("product", "idp_product_scope_release_report"),
    "build_idp_virtual_hbond_parity_packet": ("product", "idp_product_scope_hbond_parity"),
    "build_kinase_ml_live_status": ("product", "product_kinase_ml_status"),
    "build_ligand_admet_module": ("product", "product_ligand_admet"),
    "build_ligand_stage2_visual_snapshot": ("product", "product_ligand_stage2_visual"),
    "build_ligand_stress_post_report": ("product", "product_ligand_stress_report"),
    "build_p2_data_lifecycle_manifest": ("cleanup", "cleanup_p2_data_lifecycle"),
    "build_rust_hip_engine": ("product", "product_rocm_hip_engine"),
    "build_sarscov2_mpro_broad_screen_prelaunch": ("wetlab", "wetlab_sarscov2_mpro_campaign"),
    "build_selected_allatom_visual_gallery": ("product", "product_allatom_visual_gallery"),
    "build_synthetic_protein_atom_frames_fixture": ("product", "product_viewer_atom_fixture"),
    "build_target_packet": ("product", "product_target_packet"),
    "build_trajectory_engine_ranking_guard_smoke": ("product", "product_trajectory_ranking_guard"),
    "build_viewer_compare_writeback_smoke_fixture": ("product", "product_viewer_smoke_fixture"),
    "build_viewer_protein_atom_smoke_fixture": ("product", "product_viewer_smoke_fixture"),
    "build_viewer_smoke_index": ("product", "product_viewer_smoke_fixture"),
    "dry_run_p2_data_lifecycle": ("cleanup", "cleanup_p2_data_lifecycle"),
    "monitor_ligand_stress_progress": ("product", "product_ligand_stress_monitor"),
    "report_neighbor_force_parity": ("product", "product_force_parity_report"),
    "run_competition_benchmark_regeneration": ("product", "product_competition_regeneration"),
    "run_idp_virtual_hbond_rollout_eval": ("product", "idp_product_scope_hbond_rollout"),
    "run_package_b_external_defense_regeneration": ("product", "product_external_defense_regeneration"),
    "run_target_tuned_long_stability": ("product", "product_long_stability_validation"),
    "sweep_long_stability_tuning": ("product", "product_long_stability_tuning"),
    "update_closeout_latest": ("product", "product_closeout_pointer"),
}

CLAIM_BOUNDARY = (
    "Tools package batch3 other_review classification plan only; it assigns package buckets to previously "
    "unclassified lane_a batch3 rows before any move. It does not move files, rewrite imports, delete, archive, "
    "commit, push, execute selected tools, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _target_path(package: str, tool_path: str) -> str:
    return str(Path("tools") / package / Path(tool_path).name)


def build_tools_package_batch3_other_review_classification_plan(
    *,
    batch3_plan_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    batch3_plan = batch3_plan_packet or _read_json_if_present(DEFAULT_BATCH3_PLAN_JSON)
    source_rows = _rows(batch3_plan)
    candidates = [
        row
        for row in source_rows
        if _text(row.get("review_lane")) == "lane_a_zero_test_low_internal"
        and _text(row.get("proposed_package")) == "other_review"
        and not _text(row.get("target_path"))
    ]
    classified_rows: list[dict[str, Any]] = []
    for row in candidates:
        tool_path = _text(row.get("tool_path"))
        stem = Path(tool_path).stem
        decision = BATCH3_MANUAL_PACKAGE_DECISIONS.get(stem)
        if decision:
            reclassified_package, reason = decision
            status = "classified"
            keyword = f"manual_decision:{reason}"
            target_path = _target_path(reclassified_package, tool_path)
        else:
            reclassified_package = "defer_manual_review"
            status = "manual_review_required"
            keyword = "no_batch3_manual_decision"
            target_path = ""
        classified_rows.append(
            {
                **row,
                "reclassified_package": reclassified_package,
                "reclassification_keyword": keyword,
                "target_path": target_path,
                "classification_status": status,
                "move_executed": False,
                "external_state_mutated": False,
            }
        )

    package_counts = Counter(row["reclassified_package"] for row in classified_rows)
    manual_decision_count = sum(
        1 for row in classified_rows if str(row["reclassification_keyword"]).startswith("manual_decision:")
    )
    unclassified_count = sum(1 for row in classified_rows if row["classification_status"] != "classified")
    classified_count = len(classified_rows) - unclassified_count
    plan_ready = unclassified_count == 0
    summary = {
        "packet_type": "tools_package_batch3_other_review_classification_plan",
        "status": (
            "tools_package_batch3_other_review_classification_plan_ready"
            if plan_ready
            else "blocked_tools_package_batch3_other_review_classification_plan"
        ),
        "source_batch3_plan_status": _text(_summary(batch3_plan).get("status")),
        "candidate_count": len(classified_rows),
        "classified_count": classified_count,
        "unclassified_count": unclassified_count,
        "manual_decision_count": manual_decision_count,
        "manual_review_required_count": package_counts.get("defer_manual_review", 0),
        "reclassified_package_counts": dict(sorted(package_counts.items())),
        "plan_ready": plan_ready,
        "move_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No batch3 lane_a other_review rows remain to classify."
            if not classified_rows
            else "Apply reclassified batch3 package buckets in a separate approved migration slice."
            if plan_ready
            else "Resolve remaining batch3 other_review rows with manual package bucket decisions."
        ),
    }
    return {"summary": summary, "rows": classified_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch3 Other Review Classification Plan",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- classified_count: `{s['classified_count']}`",
        f"- unclassified_count: `{s['unclassified_count']}`",
        f"- manual_decision_count: `{s['manual_decision_count']}`",
        f"- reclassified_package_counts: `{s['reclassified_package_counts']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build tools package batch3 other_review classification plan.")
    parser.add_argument("--batch3-plan-json", default=DEFAULT_BATCH3_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_package_batch3_other_review_classification_plan(
        batch3_plan_packet=_read_json_if_present(args.batch3_plan_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
