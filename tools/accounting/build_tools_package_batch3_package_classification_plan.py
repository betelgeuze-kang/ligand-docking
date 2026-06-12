#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LANE_DECOMPOSITION_JSON = "runs/tools_package_batch3_lane_decomposition_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch3_package_classification_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch3_package_classification_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch3_package_classification_plan_current.md"

PACKAGE_PATTERNS: dict[str, tuple[str, ...]] = {
    "cameo": ("cameo",),
    "casp17": ("casp", "massivefold", "dockq", "lddt", "bisyrmsd"),
    "cleanup": ("cleanup", "archive", "externalize", "p2_data_lifecycle", "classify_runs_files", "prune_runs_files"),
    "gpcr_replay": ("gpcr", "adrb", "drd2", "htr2a", "oprm1", "chembl20", "rank_rescue", "replay"),
    "wetlab": (
        "wetlab",
        "alk2",
        "caix",
        "ca_ix",
        "cathepsin",
        "dpre1",
        "dengue",
        "lbdhodh",
        "stk17b",
        "tcruzi",
        "cruzi",
        "sarscov2",
        "mpro",
        "plpro",
        "broad_screen",
        "krs1",
        "dhodh",
        "assay",
        "screen",
        "render_readme_molecular_figures",
    ),
    "product": (
        "accuracy",
        "active_learning",
        "ai_",
        "allatom",
        "amd",
        "api",
        "architecture",
        "backmapping",
        "benchmark",
        "binding",
        "biorxiv",
        "bm5",
        "cath",
        "claim",
        "commercial",
        "competition",
        "customer",
        "data_science",
        "deploy",
        "docking",
        "domain",
        "execution",
        "external",
        "feature_matrix",
        "fidelity",
        "goal",
        "idp",
        "kinase",
        "ligand",
        "license",
        "md_",
        "metadata",
        "model",
        "openmm",
        "operator",
        "pdb_loader",
        "perturbed_data",
        "physics",
        "pose",
        "product",
        "protein",
        "public",
        "release",
        "residual",
        "rocm",
        "router",
        "score",
        "security",
        "sparse_checkpoints",
        "stage",
        "structure",
        "target",
        "trajectory",
        "validation",
        "viewer",
        "visualize_experiment_dashboard",
    ),
}

MANUAL_DECISIONS: dict[str, tuple[str, str, str]] = {
    "__init__": ("canonical_owner_review", "root_tools_package_init", ""),
    "append_keep_green_lane_history": ("product", "product_keep_green_history_helper", "tools/product/append_keep_green_lane_history.py"),
    "builder_json_utils": ("product", "shared_product_builder_json_helper", "tools/product/builder_json_utils.py"),
    "builder_table_utils": ("product", "shared_product_builder_table_helper", "tools/product/builder_table_utils.py"),
    "classify_runs_files": ("cleanup", "runs_cleanup_classification_helper", "tools/cleanup/classify_runs_files.py"),
    "collect_feature_matrix": ("product", "product_feature_matrix_helper", "tools/product/collect_feature_matrix.py"),
    "curate_structure_quality": ("product", "product_structure_quality_helper", "tools/product/curate_structure_quality.py"),
    "generate_perturbed_data": ("product", "product_perturbed_data_helper", "tools/product/generate_perturbed_data.py"),
    "pdb_loader": ("product", "product_structure_pdb_loader", "tools/product/pdb_loader.py"),
    "postprocess_structure_visuals": ("product", "product_structure_visual_helper", "tools/product/postprocess_structure_visuals.py"),
    "prune_runs_files": ("cleanup", "runs_cleanup_prune_helper", "tools/cleanup/prune_runs_files.py"),
    "render_readme_molecular_figures": ("wetlab", "wetlab_readme_molecular_figures", "tools/wetlab/render_readme_molecular_figures.py"),
    "report_physics_fidelity": ("product", "product_physics_fidelity_report", "tools/product/report_physics_fidelity.py"),
    "report_sparse_checkpoints": ("product", "product_sparse_checkpoint_report", "tools/product/report_sparse_checkpoints.py"),
    "smoke_alert_delivery": ("product", "product_alert_delivery_smoke", "tools/product/smoke_alert_delivery.py"),
    "speed_profile": ("product", "product_runtime_speed_profile", "tools/product/speed_profile.py"),
    "speed_profile_defaults": ("product", "product_runtime_speed_profile_defaults", "tools/product/speed_profile_defaults.py"),
}

GENERIC_PRODUCT_PREFIXES = (
    "apply_",
    "build_",
    "check_",
    "create_",
    "materialize_",
    "monitor_",
    "prepare_",
    "run_",
    "summarize_",
    "update_",
    "validate_",
)

CLAIM_BOUNDARY = (
    "Tools package batch3 package-classification plan only; it assigns package buckets to "
    "package_classification_required lane rows before any migration. It does not move files, rewrite imports, "
    "delete, archive, commit, push, execute selected tools, or mutate external state."
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
    if package == "canonical_owner_review":
        return ""
    return str(Path("tools") / package / Path(tool_path).name)


def _classify(stem: str, tool_path: str) -> tuple[str, str, str]:
    normalized = stem.lower()
    manual = MANUAL_DECISIONS.get(normalized)
    if manual:
        return manual
    for package, patterns in PACKAGE_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                return package, f"pattern:{pattern}", _target_path(package, tool_path)
    if normalized.startswith(GENERIC_PRODUCT_PREFIXES):
        return "product", "generic_product_prefix", _target_path("product", tool_path)
    return "defer_manual_review", "no_package_classification_rule", ""


def build_tools_package_batch3_package_classification_plan(
    *,
    lane_decomposition_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = lane_decomposition_packet or _read_json_if_present(DEFAULT_LANE_DECOMPOSITION_JSON)
    candidates = [
        row
        for row in _rows(packet)
        if _text(row.get("decomposition_lane")) == "package_classification_required"
    ]
    classified_rows: list[dict[str, Any]] = []
    for row in candidates:
        tool_path = _text(row.get("tool_path"))
        stem = Path(tool_path).stem
        package, reason, target_path = _classify(stem, tool_path)
        status = "classified" if package != "defer_manual_review" else "manual_review_required"
        classified_rows.append(
            {
                **row,
                "reclassified_package": package,
                "reclassification_keyword": reason,
                "target_path": target_path,
                "classification_status": status,
                "move_executed": False,
                "external_state_mutated": False,
            }
        )

    package_counts = Counter(row["reclassified_package"] for row in classified_rows)
    unclassified_count = sum(1 for row in classified_rows if row["classification_status"] != "classified")
    classified_count = len(classified_rows) - unclassified_count
    manual_decision_count = sum(
        1
        for row in classified_rows
        if not str(row["reclassification_keyword"]).startswith(("pattern:", "generic_product_prefix", "no_"))
    )
    plan_ready = unclassified_count == 0
    summary = {
        "packet_type": "tools_package_batch3_package_classification_plan",
        "status": (
            "tools_package_batch3_package_classification_plan_ready"
            if plan_ready
            else "blocked_tools_package_batch3_package_classification_plan"
        ),
        "source_lane_decomposition_status": _text(_summary(packet).get("status")),
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
            "No batch3 package_classification_required rows remain."
            if not classified_rows
            else "Use these package buckets to plan separate migration/rewrite slices; keep root package rows in canonical-owner review."
            if plan_ready
            else "Resolve remaining package_classification_required rows with explicit package decisions."
        ),
    }
    return {"summary": summary, "rows": classified_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch3 Package Classification Plan",
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
    parser = argparse.ArgumentParser(description="Build tools package batch3 package-classification plan.")
    parser.add_argument("--lane-decomposition-json", default=DEFAULT_LANE_DECOMPOSITION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_package_batch3_package_classification_plan(
        lane_decomposition_packet=_read_json_if_present(args.lane_decomposition_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
