#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

from analyze_idp_holdout_runtime import analyze as analyze_runtime
from check_idp_holdout_regression import run_check as run_regression_check


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


def _derive_global_agg_calibrator_json(manifest_json: str) -> str:
    base = os.path.basename(manifest_json)
    if "release_manifest" in base:
        derived = base.replace("release_manifest", "global_aggregation_calibrator")
        return os.path.join(os.path.dirname(manifest_json), derived)
    if manifest_json.endswith(".json"):
        return manifest_json[:-5] + "_global_aggregation_calibrator.json"
    return manifest_json + "_global_aggregation_calibrator.json"


def _load_optional_json(path: str) -> Optional[Dict[str, Any]]:
    candidate = str(path).strip()
    if not candidate or not os.path.exists(candidate):
        return None
    return _load_json(candidate)


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{100.0 * float(x):.2f}%"


def _stage_speedup_frac(
    baseline_runtime: Dict[str, Any],
    candidate_runtime: Dict[str, Any],
    stage: str,
) -> Optional[float]:
    base = float((baseline_runtime.get("stage_totals_sec") or {}).get(stage, 0.0) or 0.0)
    cand = float((candidate_runtime.get("stage_totals_sec") or {}).get(stage, 0.0) or 0.0)
    if base <= 0.0 or cand <= 0.0:
        return None
    return (base - cand) / base


def _metric_delta(baseline: Optional[float], candidate: Optional[float]) -> Optional[float]:
    if baseline is None or candidate is None:
        return None
    return float(candidate) - float(baseline)


def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    baseline_manifest = _load_json(str(args.baseline_manifest_json))
    candidate_summary = _load_json(str(args.candidate_summary_json))
    baseline_combined_metrics = dict(baseline_manifest.get("combined_gate_metrics", {}) or {})

    baseline_prefix = str(baseline_manifest.get("release_prefix", "")).strip()
    if not baseline_prefix:
        raise ValueError("baseline manifest missing release_prefix")
    candidate_summary_json = str(args.candidate_summary_json)
    candidate_prefix = (
        candidate_summary_json[:-len("_summary.json")]
        if candidate_summary_json.endswith("_summary.json")
        else os.path.splitext(candidate_summary_json)[0]
    )
    candidate_manifest_json = str(args.candidate_manifest_json).strip() or f"{candidate_prefix}_release_manifest.json"
    baseline_global_agg_json = str(args.baseline_global_agg_calibrator_json).strip() or _derive_global_agg_calibrator_json(
        str(args.baseline_manifest_json)
    )
    candidate_global_agg_json = str(args.candidate_global_agg_calibrator_json).strip() or _derive_global_agg_calibrator_json(
        candidate_manifest_json
    )
    baseline_global_agg = _load_optional_json(baseline_global_agg_json)
    candidate_global_agg = _load_optional_json(candidate_global_agg_json)

    regression_out_json = str(args.regression_json).strip()
    if not regression_out_json:
        regression_out_json = candidate_prefix + "_candidate_regression_check.json"
    regression_out_md = str(args.regression_md).strip() or _default_md_path(regression_out_json)

    regression_payload = run_regression_check(
        SimpleNamespace(
            baseline_manifest_json=str(args.baseline_manifest_json),
            candidate_summary_json=candidate_summary_json,
            out_json=regression_out_json,
            out_md=regression_out_md,
            require_candidate_pass=int(args.require_candidate_pass),
            require_all_fold_pass=int(args.require_all_fold_pass),
            max_corrected_fold_drop=int(args.max_corrected_fold_drop),
        )
    )

    baseline_runtime = analyze_runtime(baseline_prefix)
    candidate_runtime = analyze_runtime(candidate_prefix)
    candidate_combined_gate = candidate_summary.get("combined_gate", {}).get("payload", {})
    candidate_combined_metrics = {
        "branch_macro_f1": candidate_combined_gate.get("classification_metrics", {}).get("branch_macro_f1"),
        "dominant_state_accuracy": candidate_combined_gate.get("classification_metrics", {}).get("dominant_state_accuracy"),
        "llps_flag_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("llps_flag_pr_auc"),
        "llps_relevant_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("llps_relevant_pr_auc"),
        "aggregation_flag_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("aggregation_flag_pr_auc"),
        "aggregation_relevant_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("aggregation_relevant_pr_auc"),
        "compactness_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("compactness_rank_auc"),
        "helicity_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("helicity_rank_auc"),
        "condensation_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("condensation_rank_auc"),
    }

    train_eval_speedup = _stage_speedup_frac(baseline_runtime, candidate_runtime, "train_eval")
    eval_corrected_speedup = _stage_speedup_frac(baseline_runtime, candidate_runtime, "eval_corrected")
    train_branch_speedup = _stage_speedup_frac(baseline_runtime, candidate_runtime, "train_branch")

    regression_pass = bool(regression_payload.get("summary", {}).get("pass", False))
    min_train_eval_speedup = float(args.min_train_eval_speedup)
    min_eval_corrected_speedup = float(args.min_eval_corrected_speedup)

    if not regression_pass:
        recommendation = "reject_regression"
        rationale = "candidate fails release regression against current baseline"
    elif train_eval_speedup is None:
        recommendation = "hold_missing_runtime"
        rationale = "runtime analysis is incomplete; keep current baseline until full candidate timing is available"
    elif train_eval_speedup >= min_train_eval_speedup and (
        eval_corrected_speedup is None or eval_corrected_speedup >= min_eval_corrected_speedup
    ):
        recommendation = "promote_candidate"
        rationale = "candidate passes regression and shows meaningful train_eval speedup"
    elif train_eval_speedup >= 0.0:
        recommendation = "keep_baseline_insufficient_gain"
        rationale = "candidate passes regression but speedup is too small to justify baseline promotion"
    else:
        recommendation = "keep_baseline_runtime_regression"
        rationale = "candidate passes regression but slows down train_eval relative to the baseline"

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "baseline_manifest_json": str(args.baseline_manifest_json),
            "candidate_summary_json": candidate_summary_json,
            "baseline_prefix": baseline_prefix,
            "candidate_prefix": candidate_prefix,
        },
        "thresholds": {
            "require_candidate_pass": bool(args.require_candidate_pass),
            "require_all_fold_pass": bool(args.require_all_fold_pass),
            "max_corrected_fold_drop": int(args.max_corrected_fold_drop),
            "min_train_eval_speedup": min_train_eval_speedup,
            "min_eval_corrected_speedup": min_eval_corrected_speedup,
        },
        "regression": {
            "pass": regression_pass,
            "json": regression_out_json,
            "md": regression_out_md,
            "failure_count": int(regression_payload.get("summary", {}).get("failure_count", 0) or 0),
        },
        "runtime_comparison": {
            "baseline_stage_totals_sec": baseline_runtime.get("stage_totals_sec", {}),
            "candidate_stage_totals_sec": candidate_runtime.get("stage_totals_sec", {}),
            "train_eval_speedup_frac": train_eval_speedup,
            "eval_corrected_speedup_frac": eval_corrected_speedup,
            "train_branch_speedup_frac": train_branch_speedup,
        },
        "combined_metric_comparison": {
            "baseline": baseline_combined_metrics,
            "candidate": candidate_combined_metrics,
            "delta": {
                key: _metric_delta(baseline_combined_metrics.get(key), candidate_combined_metrics.get(key))
                for key in {
                    "branch_macro_f1",
                    "dominant_state_accuracy",
                    "llps_flag_pr_auc",
                    "llps_relevant_pr_auc",
                    "aggregation_flag_pr_auc",
                    "aggregation_relevant_pr_auc",
                    "compactness_rank_auc",
                    "helicity_rank_auc",
                    "condensation_rank_auc",
                }
            },
        },
        "global_aggregation_diagnostic_comparison": {
            "baseline_json": baseline_global_agg_json if baseline_global_agg is not None else "",
            "candidate_json": candidate_global_agg_json if candidate_global_agg is not None else "",
            "baseline": {
                "raw_global_aggregation_pr_auc": None
                if baseline_global_agg is None
                else baseline_global_agg.get("baseline_metrics", {}).get("raw_global_aggregation_pr_auc"),
                "calibrated_global_aggregation_pr_auc": None
                if baseline_global_agg is None
                else baseline_global_agg.get("calibrated_metrics", {}).get("oof_global_aggregation_pr_auc"),
                "raw_branch_aggregation_pr_auc": None
                if baseline_global_agg is None
                else baseline_global_agg.get("baseline_metrics", {}).get("raw_branch_aggregation_pr_auc"),
                "calibrated_branch_aggregation_pr_auc": None
                if baseline_global_agg is None
                else baseline_global_agg.get("calibrated_metrics", {}).get("oof_branch_aggregation_pr_auc"),
            },
            "candidate": {
                "raw_global_aggregation_pr_auc": None
                if candidate_global_agg is None
                else candidate_global_agg.get("baseline_metrics", {}).get("raw_global_aggregation_pr_auc"),
                "calibrated_global_aggregation_pr_auc": None
                if candidate_global_agg is None
                else candidate_global_agg.get("calibrated_metrics", {}).get("oof_global_aggregation_pr_auc"),
                "raw_branch_aggregation_pr_auc": None
                if candidate_global_agg is None
                else candidate_global_agg.get("baseline_metrics", {}).get("raw_branch_aggregation_pr_auc"),
                "calibrated_branch_aggregation_pr_auc": None
                if candidate_global_agg is None
                else candidate_global_agg.get("calibrated_metrics", {}).get("oof_branch_aggregation_pr_auc"),
            },
            "delta": {
                "raw_global_aggregation_pr_auc": _metric_delta(
                    None if baseline_global_agg is None else baseline_global_agg.get("baseline_metrics", {}).get("raw_global_aggregation_pr_auc"),
                    None if candidate_global_agg is None else candidate_global_agg.get("baseline_metrics", {}).get("raw_global_aggregation_pr_auc"),
                ),
                "calibrated_global_aggregation_pr_auc": _metric_delta(
                    None
                    if baseline_global_agg is None
                    else baseline_global_agg.get("calibrated_metrics", {}).get("oof_global_aggregation_pr_auc"),
                    None
                    if candidate_global_agg is None
                    else candidate_global_agg.get("calibrated_metrics", {}).get("oof_global_aggregation_pr_auc"),
                ),
            },
        },
        "recommendation": {
            "decision": recommendation,
            "rationale": rationale,
            "promote": recommendation == "promote_candidate",
        },
    }

    out_json = str(args.out_json)
    out_md = str(args.out_md).strip() or _default_md_path(out_json)
    _ensure_parent(out_json)
    _ensure_parent(out_md)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        bg = payload["global_aggregation_diagnostic_comparison"]["baseline"]
        cg = payload["global_aggregation_diagnostic_comparison"]["candidate"]
        bg_raw_branch = dict(bg.get("raw_branch_aggregation_pr_auc") or {})
        bg_oof_branch = dict(bg.get("calibrated_branch_aggregation_pr_auc") or {})
        cg_raw_branch = dict(cg.get("raw_branch_aggregation_pr_auc") or {})
        cg_oof_branch = dict(cg.get("calibrated_branch_aggregation_pr_auc") or {})
        f.write(
            "\n".join(
                [
                    "# IDP Release Candidate Evaluation",
                    "",
                    f"- decision: {payload['recommendation']['decision']}",
                    f"- promote: {payload['recommendation']['promote']}",
                    f"- rationale: {payload['recommendation']['rationale']}",
                    f"- regression_pass: {payload['regression']['pass']}",
                    f"- regression_failure_count: {payload['regression']['failure_count']}",
                    f"- train_eval_speedup: {_fmt_pct(train_eval_speedup)}",
                    f"- eval_corrected_speedup: {_fmt_pct(eval_corrected_speedup)}",
                    f"- train_branch_speedup: {_fmt_pct(train_branch_speedup)}",
                    f"- baseline_llps_relevant_pr_auc: {payload['combined_metric_comparison']['baseline'].get('llps_relevant_pr_auc')}",
                    f"- candidate_llps_relevant_pr_auc: {payload['combined_metric_comparison']['candidate'].get('llps_relevant_pr_auc')}",
                    f"- baseline_aggregation_relevant_pr_auc: {payload['combined_metric_comparison']['baseline'].get('aggregation_relevant_pr_auc')}",
                    f"- candidate_aggregation_relevant_pr_auc: {payload['combined_metric_comparison']['candidate'].get('aggregation_relevant_pr_auc')}",
                    f"- baseline_raw_global_aggregation_pr_auc: {payload['global_aggregation_diagnostic_comparison']['baseline'].get('raw_global_aggregation_pr_auc')}",
                    f"- candidate_raw_global_aggregation_pr_auc: {payload['global_aggregation_diagnostic_comparison']['candidate'].get('raw_global_aggregation_pr_auc')}",
                    f"- baseline_calibrated_global_aggregation_pr_auc: {payload['global_aggregation_diagnostic_comparison']['baseline'].get('calibrated_global_aggregation_pr_auc')}",
                    f"- candidate_calibrated_global_aggregation_pr_auc: {payload['global_aggregation_diagnostic_comparison']['candidate'].get('calibrated_global_aggregation_pr_auc')}",
                    f"- baseline_prefix: `{baseline_prefix}`",
                    f"- candidate_prefix: `{candidate_prefix}`",
                    f"- regression_json: `{regression_out_json}`",
                    "",
                    "## Global Aggregation Branch AP",
                    "",
                    "| Branch | Baseline Raw | Baseline OOF | Candidate Raw | Candidate OOF |",
                    "| --- | ---: | ---: | ---: | ---: |",
                    f"| aggregation_prone | {bg_raw_branch.get('aggregation_prone')} | {bg_oof_branch.get('aggregation_prone')} | {cg_raw_branch.get('aggregation_prone')} | {cg_oof_branch.get('aggregation_prone')} |",
                    f"| llps_lcd | {bg_raw_branch.get('llps_lcd')} | {bg_oof_branch.get('llps_lcd')} | {cg_raw_branch.get('llps_lcd')} | {cg_oof_branch.get('llps_lcd')} |",
                    f"| helix_tad | {bg_raw_branch.get('helix_tad')} | {bg_oof_branch.get('helix_tad')} | {cg_raw_branch.get('helix_tad')} | {cg_oof_branch.get('helix_tad')} |",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate an IDP holdout candidate against the current release baseline.")
    p.add_argument("--baseline-manifest-json", required=True, type=str)
    p.add_argument("--candidate-summary-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--out-md", default="", type=str)
    p.add_argument("--regression-json", default="", type=str)
    p.add_argument("--regression-md", default="", type=str)
    p.add_argument("--candidate-manifest-json", default="", type=str)
    p.add_argument("--baseline-global-agg-calibrator-json", default="", type=str)
    p.add_argument("--candidate-global-agg-calibrator-json", default="", type=str)
    p.add_argument("--require-candidate-pass", type=int, default=1)
    p.add_argument("--require-all-fold-pass", type=int, default=1)
    p.add_argument("--max-corrected-fold-drop", type=int, default=0)
    p.add_argument("--min-train-eval-speedup", type=float, default=0.02)
    p.add_argument("--min-eval-corrected-speedup", type=float, default=0.0)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = evaluate(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
