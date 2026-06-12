#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tools.accounting.build_tools_package_separation_work_order import PACKAGE_KEYWORDS, TARGET_PACKAGES
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_ORDER_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_other_review_classification_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_other_review_classification_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_other_review_classification_plan_current.md"

EXTENDED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "product": (
        "accounting",
        "accuracy",
        "api_",
        "benchmark",
        "commercial",
        "external",
        "goal",
        "license",
        "lit_pcba",
        "model_registry",
        "public_benchmark",
        "residual",
        "rocm",
        "runner",
        "scaleup",
        "smoke",
        "validate",
    ),
    "casp17": ("bisyrmsd", "casp", "dockq", "lddt", "massivefold"),
    "wetlab": ("assay", "broad_screen", "screen", "stk17b"),
    "cleanup": ("cleanup", "archive", "externalize", "transition_cleanup", "runs_cleanup"),
    "gpcr_replay": ("replay", "shadow", "rank_rescue", "heldout"),
    "cameo": ("cameo",),
}

MANUAL_PACKAGE_DECISIONS: dict[str, tuple[str, str]] = {
    "analyze_idp_holdout_runtime": ("product", "idp_product_scope_runtime"),
    "audit_ligand_leakage": ("product", "ligand_product_data_leakage_audit"),
    "__init__": ("canonical_owner_review", "root_tools_package_init"),
    "builder_json_utils": ("product", "shared_product_builder_json_helper"),
    "check_biorxiv_temporal_provenance_maps": ("product", "biorxiv_temporal_product_validation"),
    "check_idp_holdout_regression": ("product", "idp_product_scope_regression"),
    "check_idp_virtual_hbond_parity": ("product", "idp_product_scope_physics_parity"),
    "check_rust_hip_engine": ("product", "rocm_hip_product_engine_probe"),
    "check_strict_release_regression": ("product", "product_release_regression_gate"),
    "compare_idp_global_aggregation_calibrators": ("product", "idp_product_scope_calibration"),
    "create_percent_encoded_path_aliases": ("product", "product_local_viewer_path_helper"),
    "diagnose_ligand_stress_run": ("product", "ligand_product_runtime_diagnostic"),
    "evaluate_active_learning_priority_ab": ("product", "product_active_learning_evaluation"),
    "evaluate_allatom_equivalence_gate": ("product", "product_allatom_accuracy_gate"),
    "evaluate_idp_global_aggregation_calibrator": ("product", "idp_product_scope_calibration"),
    "evaluate_idp_release_candidate": ("product", "idp_product_scope_release_gate"),
    "evaluate_target_mts_policy": ("product", "product_ai_runtime_policy_eval"),
    "export_ai_router_onnx": ("product", "product_ai_router_export"),
    "extract_special_case_labels": ("product", "product_accuracy_label_generation"),
    "fetch_biorxiv_temporal_chembl_item_provenance": ("product", "biorxiv_temporal_product_validation"),
    "fetch_biorxiv_temporal_named_ligand_item_provenance": ("product", "biorxiv_temporal_product_validation"),
    "fetch_idp_llps_afdb_set": ("product", "idp_product_scope_source_fetch"),
    "generate_meta_tasks": ("product", "product_ai_router_training_helper"),
    "gio_wrapper": ("product", "product_local_viewer_open_helper"),
    "idp_branch_labeling": ("product", "idp_product_scope_label_helper"),
    "local_engine_surface_helpers": ("product", "product_local_engine_surface_helper"),
    "operator_surface_contracts": ("product", "product_operator_surface_contract_helper"),
    "prepare_real_drug_targets": ("product", "product_real_target_source_materialization"),
    "prepare_real_md_manifest": ("product", "product_real_md_manifest_helper"),
    "profile_ai_runtime_modes": ("product", "product_ai_runtime_profile"),
    "profile_bottlenecks": ("product", "product_runtime_bottleneck_profile"),
    "profile_idp_force_components": ("product", "idp_product_scope_force_profile"),
    "publish_openmm_2bead_release": ("product", "product_openmm_release_packaging"),
    "render_chimerax_movies": ("product", "product_molecular_rendering_asset_helper"),
    "render_live_unseen_monitor": ("product", "product_live_unseen_monitor"),
    "render_readme_molecular_figures": ("wetlab", "wetlab_tcruzi_pde_readme_figures"),
    "report_stage2_speed_bottlenecks": ("product", "product_stage2_runtime_report"),
    "report_real_md_metadata_gaps": ("product", "product_real_md_metadata_gap_report"),
    "scaffold_md_manifest": ("product", "product_md_manifest_scaffold"),
    "scaffold_real_md_source_manifest": ("product", "product_real_md_source_manifest_scaffold"),
    "simulate_ligand_gate_scenarios": ("product", "ligand_product_gate_simulation"),
    "speed_profile": ("product", "product_runtime_speed_profile"),
    "speed_profile_defaults": ("product", "product_runtime_speed_profile_defaults"),
    "summarize_ligand_gate_failure": ("product", "ligand_product_gate_failure_summary"),
    "sweep_claim_input_profiles": ("product", "product_claim_input_profile_sweep"),
    "view_idp_global_aggregation_predictions": ("product", "idp_product_scope_prediction_view"),
    "visualize_experiment_dashboard": ("product", "product_experiment_dashboard_visualization"),
    "watch_ligand_run_closeout": ("product", "ligand_product_run_closeout_watch"),
    "xdg_open_wrapper": ("product", "product_local_viewer_open_helper"),
}

CLAIM_BOUNDARY = (
    "Tools package other_review classification plan only; it reclassifies batch2 other_review rows into target "
    "package buckets before any move. It does not move files, rewrite imports, or mutate external state."
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


def _combined_keywords() -> dict[str, tuple[str, ...]]:
    combined: dict[str, tuple[str, ...]] = {}
    for package in TARGET_PACKAGES:
        merged = tuple(dict.fromkeys([*PACKAGE_KEYWORDS[package], *EXTENDED_KEYWORDS.get(package, ())]))
        combined[package] = merged
    return combined


def _classify_extended(stem: str) -> tuple[str, str]:
    normalized = stem.lower()
    manual = MANUAL_PACKAGE_DECISIONS.get(normalized)
    if manual:
        return manual[0], f"manual_decision:{manual[1]}"
    for package, keywords in _combined_keywords().items():
        for keyword in keywords:
            if keyword in normalized:
                return package, keyword
    if normalized.startswith("build_"):
        return "product", "build_prefix"
    if normalized.startswith("run_"):
        return "product", "run_prefix"
    if re.search(r"(monitor|launch|apply|repair|promote|materialize|autofill|resolve)_", normalized):
        return "product", "ops_verb_prefix"
    return "defer_manual_review", "no_extended_keyword_match"


def build_tools_package_other_review_classification_plan(
    *,
    work_order_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    work_order = work_order_packet or _read_json_if_present(DEFAULT_WORK_ORDER_JSON)
    source_rows = _rows(work_order)
    candidates = [
        row
        for row in source_rows
        if _text(row.get("proposed_package")) == "other_review" and _text(row.get("migration_batch")) == "batch_2_review"
    ]
    classified_rows: list[dict[str, Any]] = []
    for row in candidates:
        tool_path = _text(row.get("tool_path"))
        stem = Path(tool_path).stem
        reclassified_package, matched_keyword = _classify_extended(stem)
        classified_rows.append(
            {
                **row,
                "reclassified_package": reclassified_package,
                "reclassification_keyword": matched_keyword,
                "classification_status": "classified" if reclassified_package != "defer_manual_review" else "manual_review_required",
                "move_executed": False,
                "external_state_mutated": False,
            }
        )
    unclassified_count = sum(1 for row in classified_rows if row["classification_status"] != "classified")
    classified_count = len(classified_rows) - unclassified_count
    package_counts = Counter(row["reclassified_package"] for row in classified_rows)
    manual_decision_count = sum(
        1 for row in classified_rows if str(row["reclassification_keyword"]).startswith("manual_decision:")
    )
    plan_ready = unclassified_count == 0
    status = "tools_package_other_review_classification_plan_ready" if plan_ready else "blocked_tools_package_other_review_classification_plan"
    summary = {
        "packet_type": "tools_package_other_review_classification_plan",
        "status": status,
        "candidate_count": len(classified_rows),
        "classified_count": classified_count,
        "unclassified_count": unclassified_count,
        "manual_review_required_count": package_counts.get("defer_manual_review", 0),
        "manual_decision_count": manual_decision_count,
        "reclassified_package_counts": dict(sorted(package_counts.items())),
        "plan_ready": plan_ready,
        "move_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "No batch2 other_review rows remain to classify."
            if not classified_rows
            else "Apply reclassified package buckets in a separate approved tools migration slice."
            if plan_ready
            else "Resolve remaining other_review rows with manual package bucket decisions."
        ),
    }
    return {"summary": summary, "rows": classified_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Other Review Classification Plan",
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
    parser = argparse.ArgumentParser(description="Build tools package other_review classification plan.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_package_other_review_classification_plan(
        work_order_packet=_read_json_if_present(args.work_order_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
