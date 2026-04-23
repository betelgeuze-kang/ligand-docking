#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _replace_symlink(link_path: str, target_path: str) -> None:
    link = Path(link_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    rel_target = os.path.relpath(target_path, start=str(link.parent))
    link.symlink_to(rel_target)


def _infer_prefix(summary_json: str) -> str:
    if summary_json.endswith("_summary.json"):
        return summary_json[: -len("_summary.json")]
    return os.path.splitext(summary_json)[0]


def promote(args: argparse.Namespace) -> Dict[str, Any]:
    summary_json = str(args.summary_json).strip()
    if not summary_json:
        raise ValueError("--summary-json is required")
    summary = _load_json(summary_json)
    if not bool(summary.get("pass", False)):
        raise ValueError(f"smoke summary is not passing: {summary_json}")

    prefix = _infer_prefix(summary_json)
    release_label = str(args.release_label).strip() or Path(prefix).name
    manifest_json = str(args.manifest_json).strip() or f"{prefix}_release_manifest.json"
    manifest_md = str(args.manifest_md).strip() or f"{prefix}_release_manifest.md"
    regression_json = str(args.regression_json).strip() or f"{prefix}_release_regression.json"
    regression_md = str(args.regression_md).strip() or f"{prefix}_release_regression.md"
    candidate_eval_json = str(args.candidate_eval_json).strip() or f"{prefix}_release_candidate_eval.json"
    candidate_eval_md = str(args.candidate_eval_md).strip() or f"{prefix}_release_candidate_eval.md"
    runner_json = str(args.runner_json).strip() or f"{prefix}_runner.json"
    runner_md = str(args.runner_md).strip() or f"{prefix}_runner.md"
    baseline_manifest_json = str(args.smoke_baseline_manifest_json).strip() or f"{prefix}_baseline_manifest.json"
    calibrator_json = str(args.global_aggregation_calibrator_json).strip() or (
        f"{prefix}_global_aggregation_calibrator.json"
    )
    calibrator_md = str(args.global_aggregation_calibrator_md).strip() or (
        f"{prefix}_global_aggregation_calibrator.md"
    )
    predictions_csv = str(args.global_aggregation_predictions_csv).strip() or (
        f"{prefix}_global_aggregation_calibrator_predictions.csv"
    )
    dashboard_html = str(args.global_aggregation_dashboard_html).strip() or (
        f"{prefix}_global_aggregation_dashboard.html"
    )
    dashboard_json = str(args.global_aggregation_dashboard_json).strip() or (
        f"{prefix}_global_aggregation_dashboard.json"
    )

    smoke_current_json = str(args.smoke_current_json)
    summary_current_json = str(args.summary_current_json)
    summary_current_md = str(args.summary_current_md)
    manifest_current_json = str(args.manifest_current_json)
    manifest_current_md = str(args.manifest_current_md)
    regression_current_json = str(args.regression_current_json)
    regression_current_md = str(args.regression_current_md)
    candidate_eval_current_json = str(args.candidate_eval_current_json)
    candidate_eval_current_md = str(args.candidate_eval_current_md)
    runner_current_json = str(args.runner_current_json)
    runner_current_md = str(args.runner_current_md)
    baseline_manifest_current_json = str(args.smoke_baseline_manifest_current_json)
    calibrator_current_json = str(args.global_aggregation_calibrator_current_json)
    calibrator_current_md = str(args.global_aggregation_calibrator_current_md)
    predictions_current_csv = str(args.global_aggregation_predictions_current_csv)
    dashboard_current_html = str(args.global_aggregation_dashboard_current_html)
    dashboard_current_json = str(args.global_aggregation_dashboard_current_json)

    current_payload = {
        "release_label": release_label,
        "summary_json": summary_json,
        "summary_md": f"{prefix}_summary.md",
        "manifest_json": manifest_json,
        "manifest_md": manifest_md,
        "regression_json": regression_json,
        "regression_md": regression_md,
        "candidate_eval_json": candidate_eval_json,
        "candidate_eval_md": candidate_eval_md,
        "runner_json": runner_json,
        "runner_md": runner_md,
        "smoke_baseline_manifest_json": baseline_manifest_json,
        "global_aggregation_calibrator_json": calibrator_json,
        "global_aggregation_calibrator_md": calibrator_md,
        "global_aggregation_predictions_csv": predictions_csv,
        "global_aggregation_dashboard_html": dashboard_html,
        "global_aggregation_dashboard_json": dashboard_json,
        "promoted_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "notes": (
            "Canonical current IDP smoke reference. "
            "Use smoke_baseline_manifest_json for smoke regression comparisons and "
            "baseline release manifest for frozen-label sourcing."
        ),
    }
    _write_json(smoke_current_json, current_payload)

    _replace_symlink(summary_current_json, summary_json)
    _replace_symlink(summary_current_md, f"{prefix}_summary.md")
    _replace_symlink(manifest_current_json, manifest_json)
    _replace_symlink(manifest_current_md, manifest_md)
    _replace_symlink(regression_current_json, regression_json)
    _replace_symlink(regression_current_md, regression_md)
    _replace_symlink(candidate_eval_current_json, candidate_eval_json)
    _replace_symlink(candidate_eval_current_md, candidate_eval_md)
    _replace_symlink(runner_current_json, runner_json)
    _replace_symlink(runner_current_md, runner_md)
    _replace_symlink(baseline_manifest_current_json, baseline_manifest_json)
    _replace_symlink(calibrator_current_json, calibrator_json)
    _replace_symlink(calibrator_current_md, calibrator_md)
    _replace_symlink(predictions_current_csv, predictions_csv)
    _replace_symlink(dashboard_current_html, dashboard_html)
    _replace_symlink(dashboard_current_json, dashboard_json)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "updated": True,
        "release_label": release_label,
        "summary_json": summary_json,
        "smoke_current_json": smoke_current_json,
        "summary_current_json": summary_current_json,
        "manifest_current_json": manifest_current_json,
        "regression_current_json": regression_current_json,
    }
    _write_json(str(args.out_json), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Promote a passing smoke regression run to the canonical current smoke reference.")
    p.add_argument("--summary-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--release-label", default="", type=str)
    p.add_argument("--manifest-json", default="", type=str)
    p.add_argument("--manifest-md", default="", type=str)
    p.add_argument("--regression-json", default="", type=str)
    p.add_argument("--regression-md", default="", type=str)
    p.add_argument("--candidate-eval-json", default="", type=str)
    p.add_argument("--candidate-eval-md", default="", type=str)
    p.add_argument("--runner-json", default="", type=str)
    p.add_argument("--runner-md", default="", type=str)
    p.add_argument("--smoke-baseline-manifest-json", default="", type=str)
    p.add_argument("--global-aggregation-calibrator-json", default="", type=str)
    p.add_argument("--global-aggregation-calibrator-md", default="", type=str)
    p.add_argument("--global-aggregation-predictions-csv", default="", type=str)
    p.add_argument("--global-aggregation-dashboard-html", default="", type=str)
    p.add_argument("--global-aggregation-dashboard-json", default="", type=str)
    p.add_argument("--smoke-current-json", default="runs/idp_3bead_release_smoke_current.json", type=str)
    p.add_argument("--summary-current-json", default="runs/idp_3bead_release_smoke_summary_current.json", type=str)
    p.add_argument("--summary-current-md", default="runs/idp_3bead_release_smoke_summary_current.md", type=str)
    p.add_argument("--manifest-current-json", default="runs/idp_3bead_release_smoke_manifest_current.json", type=str)
    p.add_argument("--manifest-current-md", default="runs/idp_3bead_release_smoke_manifest_current.md", type=str)
    p.add_argument("--regression-current-json", default="runs/idp_3bead_release_smoke_regression_current.json", type=str)
    p.add_argument("--regression-current-md", default="runs/idp_3bead_release_smoke_regression_current.md", type=str)
    p.add_argument("--candidate-eval-current-json", default="runs/idp_3bead_release_smoke_candidate_eval_current.json", type=str)
    p.add_argument("--candidate-eval-current-md", default="runs/idp_3bead_release_smoke_candidate_eval_current.md", type=str)
    p.add_argument("--runner-current-json", default="runs/idp_3bead_release_smoke_runner_current.json", type=str)
    p.add_argument("--runner-current-md", default="runs/idp_3bead_release_smoke_runner_current.md", type=str)
    p.add_argument("--smoke-baseline-manifest-current-json", default="runs/idp_3bead_release_smoke_baseline_manifest_current.json", type=str)
    p.add_argument("--global-aggregation-calibrator-current-json", default="runs/idp_3bead_release_smoke_global_aggregation_calibrator_current.json", type=str)
    p.add_argument("--global-aggregation-calibrator-current-md", default="runs/idp_3bead_release_smoke_global_aggregation_calibrator_current.md", type=str)
    p.add_argument("--global-aggregation-predictions-current-csv", default="runs/idp_3bead_release_smoke_global_aggregation_predictions_current.csv", type=str)
    p.add_argument("--global-aggregation-dashboard-current-html", default="runs/idp_3bead_release_smoke_global_aggregation_dashboard_current.html", type=str)
    p.add_argument("--global-aggregation-dashboard-current-json", default="runs/idp_3bead_release_smoke_global_aggregation_dashboard_current.json", type=str)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = promote(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
