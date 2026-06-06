#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_PATCH_ENV = {
    "IDP_R11_ML_PATCH": "0",
    "IDP_R11_PHYS_PATCH": "0",
    "IDP_R12_ML_PATCH": "0",
    "IDP_R12_PHYS_PATCH": "0",
    "IDP_R13_ML_PATCH": "0",
    "IDP_R13_PHYS_PATCH": "0",
    "IDP_R14_ML_PATCH": "0",
    "IDP_R14_PHYS_PATCH": "1",
    "IDP_R15_ML_PATCH": "0",
    "IDP_R16_ML_PATCH": "1",
    "IDP_R17_PHYS_PATCH": "0",
}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _default_md_path(out_json: str) -> str:
    if out_json.endswith(".json"):
        return out_json[:-5] + ".md"
    return out_json + ".md"


def _infer_prefix(summary_json: str) -> str:
    if summary_json.endswith("_summary.json"):
        return summary_json[: -len("_summary.json")]
    return os.path.splitext(summary_json)[0]


def _derive_global_agg_paths(manifest_json: str, prefix: str) -> Dict[str, str]:
    if "release_manifest" in os.path.basename(manifest_json):
        base_json = manifest_json.replace("release_manifest", "global_aggregation_calibrator")
    else:
        base_json = f"{prefix}_global_aggregation_calibrator.json"
    return {
        "json": base_json,
        "md": base_json[:-5] + ".md" if base_json.endswith(".json") else base_json + ".md",
        "predictions_csv": base_json[:-5] + "_predictions.csv"
        if base_json.endswith(".json")
        else base_json + "_predictions.csv",
    }


def _derive_global_agg_dashboard_paths(manifest_json: str, prefix: str) -> Dict[str, str]:
    if "release_manifest" in os.path.basename(manifest_json):
        base_html = manifest_json.replace("release_manifest", "global_aggregation_dashboard")
        if base_html.endswith(".json"):
            base_html = base_html[:-5] + ".html"
    else:
        base_html = f"{prefix}_global_aggregation_dashboard.html"
    base_json = base_html[:-5] + ".json" if base_html.endswith(".html") else base_html + ".json"
    return {"html": base_html, "json": base_json}


def _derive_targets_csv(eval_corrected_json: str) -> str:
    if eval_corrected_json.endswith("_summary.json"):
        return eval_corrected_json[: -len("_summary.json")] + "_targets.csv"
    return os.path.splitext(eval_corrected_json)[0] + "_targets.csv"


def _fold_artifacts(prefix: str, folds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, fold in enumerate(folds, start=1):
        holdout = str(fold.get("holdout", f"fold{idx}")).strip()
        fold_prefix = f"{prefix}_fold{idx}_{holdout}"
        out.append(
            {
                "fold_index": int(idx),
                "holdout": holdout,
                "pass": bool(fold.get("pass", False)),
                "baseline_gate_pass": bool(fold.get("baseline_gate", {}).get("pass", False)),
                "corrected_gate_pass": bool(fold.get("corrected_gate", {}).get("pass", False)),
                "corrected_gate_json": f"{fold_prefix}_gate_corrected_summary.json",
                "baseline_gate_json": f"{fold_prefix}_gate_baseline_summary.json",
                "eval_corrected_json": f"{fold_prefix}_eval_corrected_summary.json",
                "eval_corrected_csv": _derive_targets_csv(f"{fold_prefix}_eval_corrected_summary.json"),
                "train_branch_json": f"{fold_prefix}_train_branch_summary.json",
            }
        )
    return out


def build_manifest(args: argparse.Namespace) -> Dict[str, Any]:
    summary_json = str(args.summary_json)
    summary = _load_json(summary_json)
    prefix = _infer_prefix(summary_json)
    release_label = str(args.release_label).strip() or os.path.basename(prefix)
    out_json = str(args.out_json)
    out_md = str(args.out_md).strip() or _default_md_path(out_json)
    diag_paths = _derive_global_agg_paths(out_json, prefix)
    dashboard_paths = _derive_global_agg_dashboard_paths(out_json, prefix)

    combined_gate_payload = summary.get("combined_gate", {}).get("payload", {})
    fold_count = int(summary.get("fold_count", 0))
    corrected_pass_folds = int(summary.get("corrected_pass_folds", 0))
    all_fold_pass = bool(summary.get("all_fold_pass", corrected_pass_folds == fold_count))
    combined_gate_pass = bool(summary.get("combined_gate_pass", False))

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "release_kind": "idp_3bead_holdout_release",
        "release_label": release_label,
        "release_prefix": prefix,
        "summary_json": summary_json,
        "summary_md": f"{prefix}_summary.md",
        "combined_gate_json": f"{prefix}_combined_gate_summary.json",
        "combined_gate_md": f"{prefix}_combined_gate_summary.md",
        "config_json": str(summary.get("config_json", "")),
        "device": str(summary.get("device", "")),
        "holdout_key": str(summary.get("holdout_key", "")),
        "patch_env_defaults": dict(DEFAULT_PATCH_ENV),
        "acceptance": {
            "pass": bool(summary.get("pass", False)),
            "all_fold_pass": all_fold_pass,
            "combined_gate_pass": combined_gate_pass,
            "fold_count": fold_count,
            "baseline_pass_folds": int(summary.get("baseline_pass_folds", 0)),
            "corrected_pass_folds": corrected_pass_folds,
        },
        "combined_gate_metrics": {
            "branch_macro_f1": combined_gate_payload.get("classification_metrics", {}).get("branch_macro_f1"),
            "dominant_state_accuracy": combined_gate_payload.get("classification_metrics", {}).get("dominant_state_accuracy"),
            "llps_flag_pr_auc": combined_gate_payload.get("classification_metrics", {}).get("llps_flag_pr_auc"),
            "llps_relevant_pr_auc": combined_gate_payload.get("classification_metrics", {}).get("llps_relevant_pr_auc"),
            "aggregation_flag_pr_auc": combined_gate_payload.get("classification_metrics", {}).get("aggregation_flag_pr_auc"),
            "aggregation_relevant_pr_auc": combined_gate_payload.get("classification_metrics", {}).get("aggregation_relevant_pr_auc"),
            "compactness_rank_auc": combined_gate_payload.get("ranking_metrics", {}).get("compactness_rank_auc"),
            "helicity_rank_auc": combined_gate_payload.get("ranking_metrics", {}).get("helicity_rank_auc"),
            "condensation_rank_auc": combined_gate_payload.get("ranking_metrics", {}).get("condensation_rank_auc"),
        },
        "combined_physics_summary": combined_gate_payload.get("physics_summary", {}),
        "fold_artifacts": _fold_artifacts(prefix, list(summary.get("folds", []))),
    }
    diagnostic_artifacts = {
        "global_aggregation_calibrator_json": diag_paths["json"],
        "global_aggregation_calibrator_md": diag_paths["md"],
        "global_aggregation_predictions_csv": diag_paths["predictions_csv"],
        "global_aggregation_dashboard_html": dashboard_paths["html"],
        "global_aggregation_dashboard_json": dashboard_paths["json"],
    }
    if any(os.path.exists(path) for path in diagnostic_artifacts.values()):
        payload["diagnostic_artifacts"] = diagnostic_artifacts

    _ensure_parent(out_json)
    _ensure_parent(out_md)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Release Manifest",
                    "",
                    f"- release_label: {payload['release_label']}",
                    f"- pass: {payload['acceptance']['pass']}",
                    f"- all_fold_pass: {payload['acceptance']['all_fold_pass']}",
                    f"- combined_gate_pass: {payload['acceptance']['combined_gate_pass']}",
                    f"- fold_count: {payload['acceptance']['fold_count']}",
                    f"- corrected_pass_folds: {payload['acceptance']['corrected_pass_folds']}",
                    f"- combined_physics_failed_rows: {payload.get('combined_physics_summary', {}).get('failed_row_count', 0)}",
                    f"- combined_physics_hotspots: {payload.get('combined_physics_summary', {}).get('unique_hotspot_count', 0)}",
                    f"- summary_json: `{payload['summary_json']}`",
                    f"- combined_gate_json: `{payload['combined_gate_json']}`",
                    f"- config_json: `{payload['config_json']}`",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a frozen release manifest from an IDP holdout summary.")
    p.add_argument("--summary-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--out-md", default="", type=str)
    p.add_argument("--release-label", default="", type=str)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_manifest(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
