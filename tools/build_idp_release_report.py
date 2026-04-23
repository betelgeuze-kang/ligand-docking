#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _write_text(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def _derive_global_agg_calibrator_json(manifest_json: str) -> str:
    base = os.path.basename(manifest_json)
    if "release_manifest" in base:
        derived = base.replace("release_manifest", "global_aggregation_calibrator")
        return os.path.join(os.path.dirname(manifest_json), derived)
    if manifest_json.endswith(".json"):
        return manifest_json[:-5] + "_global_aggregation_calibrator.json"
    return manifest_json + "_global_aggregation_calibrator.json"


def _resolve_manifest_diag_path(manifest: Dict[str, Any], key: str) -> str:
    diag = dict(manifest.get("diagnostic_artifacts", {}) or {})
    return str(diag.get(key, "")).strip()


def build_report(
    *,
    baseline_json: str,
    manifest_json: str,
    regression_json: str,
    aggregation_calibrator_json: str = "",
    historical_compare_json: str = "",
) -> str:
    baseline = _read_json(baseline_json)
    manifest = _read_json(manifest_json)
    regression = _read_json(regression_json)
    calibrator_json = (
        str(aggregation_calibrator_json).strip()
        or _resolve_manifest_diag_path(manifest, "global_aggregation_calibrator_json")
        or _derive_global_agg_calibrator_json(manifest_json)
    )
    calibrator: Optional[Dict[str, Any]] = None
    if calibrator_json and os.path.exists(calibrator_json):
        calibrator = _read_json(calibrator_json)
    compare_json = str(historical_compare_json).strip()
    compare_payload: Optional[Dict[str, Any]] = None
    if compare_json and os.path.exists(compare_json):
        compare_payload = _read_json(compare_json)

    acceptance = dict(manifest.get("acceptance", {}) or {})
    metrics = dict(manifest.get("combined_gate_metrics", {}) or {})
    physics = dict(manifest.get("combined_physics_summary", {}) or {})
    release_label = manifest.get("release_label", "")
    summary_json = manifest.get("summary_json", "")
    dashboard_html = _resolve_manifest_diag_path(manifest, "global_aggregation_dashboard_html")
    dashboard_json = _resolve_manifest_diag_path(manifest, "global_aggregation_dashboard_json")

    lines = [
        "# IDP Release Report",
        "",
        f"- release_label: `{release_label}`",
        f"- promoted_at_local: `{baseline.get('promoted_at_local', '')}`",
        f"- summary_json: `{summary_json}`",
        f"- manifest_json: `{manifest_json}`",
        f"- regression_json: `{regression_json}`",
        f"- dashboard_html: `{dashboard_html}`" if dashboard_html else "- dashboard_html: `n/a`",
        f"- dashboard_json: `{dashboard_json}`" if dashboard_json else "- dashboard_json: `n/a`",
        "",
        "## Release Verdict",
        "",
        f"- pass: `{acceptance.get('pass')}`",
        f"- all_fold_pass: `{acceptance.get('all_fold_pass')}`",
        f"- combined_gate_pass: `{acceptance.get('combined_gate_pass')}`",
        f"- corrected_pass_folds: `{acceptance.get('corrected_pass_folds')}` / `{acceptance.get('fold_count')}`",
        f"- baseline_pass_folds: `{acceptance.get('baseline_pass_folds')}` / `{acceptance.get('fold_count')}`",
        "",
        "## Combined Metrics",
        "",
    ]
    for key in (
        "branch_macro_f1",
        "dominant_state_accuracy",
        "llps_flag_pr_auc",
        "llps_relevant_pr_auc",
        "aggregation_flag_pr_auc",
        "aggregation_relevant_pr_auc",
        "compactness_rank_auc",
        "helicity_rank_auc",
        "condensation_rank_auc",
    ):
        if key in metrics:
            lines.append(f"- {key}: `{_fmt(metrics[key])}`")

    if calibrator:
        baseline_metrics = dict(calibrator.get("baseline_metrics", {}) or {})
        calibrated_metrics = dict(calibrator.get("calibrated_metrics", {}) or {})
        raw_branch = dict(baseline_metrics.get("raw_branch_aggregation_pr_auc", {}) or {})
        oof_branch = dict(calibrated_metrics.get("oof_branch_aggregation_pr_auc", {}) or {})
        lines.extend(
            [
                "",
                "## Global Aggregation Diagnostic",
                "",
                f"- raw_global_aggregation_pr_auc: `{_fmt(baseline_metrics.get('raw_global_aggregation_pr_auc'))}`",
                f"- calibrated_global_aggregation_pr_auc_oof: `{_fmt(calibrated_metrics.get('oof_global_aggregation_pr_auc'))}`",
                f"- improvement_vs_raw_global_pr_auc: `{_fmt(calibrated_metrics.get('improvement_vs_raw_global_pr_auc'))}`",
                f"- note: {calibrator.get('recommendation', {}).get('note', '')}",
                f"- diagnostic_artifact_json: `{calibrator_json}`",
                "",
                "### Branch Aggregation AP",
                "",
                "| Branch | Raw AP | Calibrated OOF AP |",
                "| --- | ---: | ---: |",
                f"| aggregation_prone | `{_fmt(raw_branch.get('aggregation_prone'))}` | `{_fmt(oof_branch.get('aggregation_prone'))}` |",
                f"| llps_lcd | `{_fmt(raw_branch.get('llps_lcd'))}` | `{_fmt(oof_branch.get('llps_lcd'))}` |",
                f"| helix_tad | `{_fmt(raw_branch.get('helix_tad'))}` | `{_fmt(oof_branch.get('helix_tad'))}` |",
                "",
            ]
        )

    if compare_payload:
        comparison_rows = list(compare_payload.get("comparison", []) or [])
        if comparison_rows:
            lines.extend(
                [
                    "",
                    "## Historical Global Aggregation Comparison",
                    "",
                    f"- comparison_json: `{compare_json}`",
                    "",
                    "| Release | Raw Global AP | Calibrated Global AP | Improvement | Agg OOF | LLPS OOF | Helix OOF |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                ]
            )
            for row in comparison_rows:
                lines.append(
                    "| "
                    + f"`{row.get('release_label', '')}` | "
                    + f"`{_fmt(row.get('raw_global_aggregation_pr_auc'))}` | "
                    + f"`{_fmt(row.get('calibrated_global_aggregation_pr_auc'))}` | "
                    + f"`{_fmt(row.get('improvement_vs_raw_global_pr_auc'))}` | "
                    + f"`{_fmt(row.get('oof_aggregation_prone_ap'))}` | "
                    + f"`{_fmt(row.get('oof_llps_lcd_ap'))}` | "
                    + f"`{_fmt(row.get('oof_helix_tad_ap'))}` |"
                )
            lines.append("")

    lines.extend(
        [
            "",
            "## Physics Summary",
            "",
            f"- failed_row_count: `{physics.get('failed_row_count')}`",
            f"- unique_hotspot_count: `{physics.get('unique_hotspot_count')}`",
            f"- anchor_status_counts: `{physics.get('anchor_status_counts', {})}`",
            "",
            "## Regression",
            "",
            f"- pass: `{regression.get('summary', {}).get('pass')}`",
            f"- failure_count: `{regression.get('summary', {}).get('failure_count')}`",
            f"- note: {regression.get('summary', {}).get('note', '')}",
            "- mixed-branch combined gate uses branch-conditioned relevant PR-AUC metrics",
            "",
            "## Allowed Claims",
            "",
            "- `20/20 fold-level holdout pass`",
            "- `all_fold_pass = true` is the release criterion",
            "- `combined_gate_pass = true` under branch-conditioned combined metrics",
            "- `physics_summary.failed_row_count = 0` for the promoted baseline",
            "",
            "## Disallowed Claims",
            "",
            "- `combined macro aggregation PR-AUC passed release threshold`",
            "- `absolute Rg/SASA accuracy is production-grade across all targets`",
            "- `fully autonomous without expert review`",
            "- `generic_nonbonded replacement is adopted in the release baseline`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description="Build current IDP release report.")
    p.add_argument("--baseline-json", required=True)
    p.add_argument("--manifest-json", required=True)
    p.add_argument("--regression-json", required=True)
    p.add_argument("--aggregation-calibrator-json", default="")
    p.add_argument("--historical-compare-json", default="")
    p.add_argument("--out-md", required=True)
    args = p.parse_args()

    text = build_report(
        baseline_json=str(args.baseline_json),
        manifest_json=str(args.manifest_json),
        regression_json=str(args.regression_json),
        aggregation_calibrator_json=str(args.aggregation_calibrator_json),
        historical_compare_json=str(args.historical_compare_json),
    )
    _write_text(str(args.out_md), text)
    print(str(args.out_md))


if __name__ == "__main__":
    main()
