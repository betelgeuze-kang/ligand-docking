#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence


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


def _fail(
    failures: List[Dict[str, Any]],
    metric: str,
    baseline: Any,
    candidate: Any,
    threshold: Any,
    condition: str,
) -> None:
    failures.append(
        {
            "metric": str(metric),
            "baseline": baseline,
            "candidate": candidate,
            "threshold": threshold,
            "condition": str(condition),
        }
    )


def run_check(args: argparse.Namespace) -> Dict[str, Any]:
    baseline_manifest = _load_json(str(args.baseline_manifest_json))
    candidate_summary = _load_json(str(args.candidate_summary_json))

    baseline_accept = baseline_manifest.get("acceptance", {})
    baseline_fold_count = int(baseline_accept.get("fold_count", 0))
    baseline_corrected_pass = int(baseline_accept.get("corrected_pass_folds", 0))
    baseline_all_fold_pass = bool(baseline_accept.get("all_fold_pass", False))

    candidate_fold_count = int(candidate_summary.get("fold_count", 0))
    candidate_corrected_pass = int(candidate_summary.get("corrected_pass_folds", 0))
    candidate_all_fold_pass = bool(
        candidate_summary.get("all_fold_pass", candidate_corrected_pass == candidate_fold_count)
    )
    candidate_pass = bool(candidate_summary.get("pass", False))
    candidate_combined_gate_pass = bool(candidate_summary.get("combined_gate_pass", False))
    candidate_combined_gate = candidate_summary.get("combined_gate", {}).get("payload", {})

    failures: List[Dict[str, Any]] = []

    if candidate_fold_count != baseline_fold_count:
        _fail(
            failures,
            metric="fold_count",
            baseline=baseline_fold_count,
            candidate=candidate_fold_count,
            threshold=baseline_fold_count,
            condition="candidate fold_count must equal baseline fold_count",
        )

    min_corrected_pass = baseline_corrected_pass - int(args.max_corrected_fold_drop)
    if candidate_corrected_pass < min_corrected_pass:
        _fail(
            failures,
            metric="corrected_pass_folds",
            baseline=baseline_corrected_pass,
            candidate=candidate_corrected_pass,
            threshold=min_corrected_pass,
            condition="candidate corrected_pass_folds must stay within max_corrected_fold_drop",
        )

    if bool(args.require_candidate_pass) and (not candidate_pass):
        _fail(
            failures,
            metric="summary.pass",
            baseline=bool(baseline_accept.get("pass", False)),
            candidate=candidate_pass,
            threshold=True,
            condition="candidate top-level summary pass must be true",
        )

    if bool(args.require_all_fold_pass):
        required_all_fold_pass = baseline_all_fold_pass or bool(args.require_all_fold_pass)
        if required_all_fold_pass and (not candidate_all_fold_pass):
            _fail(
                failures,
                metric="all_fold_pass",
                baseline=baseline_all_fold_pass,
                candidate=candidate_all_fold_pass,
                threshold=True,
                condition="candidate all_fold_pass must be true",
            )

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "baseline_manifest_json": str(args.baseline_manifest_json),
            "candidate_summary_json": str(args.candidate_summary_json),
        },
        "thresholds": {
            "require_candidate_pass": bool(args.require_candidate_pass),
            "require_all_fold_pass": bool(args.require_all_fold_pass),
            "max_corrected_fold_drop": int(args.max_corrected_fold_drop),
        },
        "baseline": {
            "release_label": baseline_manifest.get("release_label"),
            "fold_count": baseline_fold_count,
            "corrected_pass_folds": baseline_corrected_pass,
            "all_fold_pass": baseline_all_fold_pass,
            "combined_gate_pass": bool(baseline_accept.get("combined_gate_pass", False)),
        },
        "candidate": {
            "fold_count": candidate_fold_count,
            "corrected_pass_folds": candidate_corrected_pass,
            "all_fold_pass": candidate_all_fold_pass,
            "pass": candidate_pass,
            "combined_gate_pass": candidate_combined_gate_pass,
            "combined_gate_metrics": {
                "branch_macro_f1": candidate_combined_gate.get("classification_metrics", {}).get("branch_macro_f1"),
                "dominant_state_accuracy": candidate_combined_gate.get("classification_metrics", {}).get("dominant_state_accuracy"),
                "llps_flag_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("llps_flag_pr_auc"),
                "llps_relevant_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("llps_relevant_pr_auc"),
                "aggregation_flag_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("aggregation_flag_pr_auc"),
                "aggregation_relevant_pr_auc": candidate_combined_gate.get("classification_metrics", {}).get("aggregation_relevant_pr_auc"),
                "compactness_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("compactness_rank_auc"),
                "helicity_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("helicity_rank_auc"),
                "condensation_rank_auc": candidate_combined_gate.get("ranking_metrics", {}).get("condensation_rank_auc"),
            },
        },
        "summary": {
            "pass": len(failures) == 0,
            "failure_count": len(failures),
            "note": "fold-level pass remains the release criterion; mixed-branch combined gate uses branch-conditioned relevant PR-AUC metrics",
        },
        "failures": failures,
    }

    out_json = str(args.out_json)
    out_md = str(args.out_md).strip() or _default_md_path(out_json)
    _ensure_parent(out_json)
    _ensure_parent(out_md)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Holdout Regression Check",
                    "",
                    f"- pass: {payload['summary']['pass']}",
                    f"- failure_count: {payload['summary']['failure_count']}",
                    f"- baseline_release: {payload['baseline']['release_label']}",
                    f"- baseline_corrected_pass_folds: {payload['baseline']['corrected_pass_folds']}",
                    f"- candidate_corrected_pass_folds: {payload['candidate']['corrected_pass_folds']}",
                    f"- baseline_all_fold_pass: {payload['baseline']['all_fold_pass']}",
                    f"- candidate_all_fold_pass: {payload['candidate']['all_fold_pass']}",
                    f"- candidate_combined_gate_pass: {payload['candidate']['combined_gate_pass']}",
                    f"- candidate_llps_relevant_pr_auc: {payload['candidate']['combined_gate_metrics'].get('llps_relevant_pr_auc')}",
                    f"- candidate_aggregation_relevant_pr_auc: {payload['candidate']['combined_gate_metrics'].get('aggregation_relevant_pr_auc')}",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Check an IDP holdout summary against a frozen release manifest.")
    p.add_argument("--baseline-manifest-json", required=True, type=str)
    p.add_argument("--candidate-summary-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--out-md", default="", type=str)
    p.add_argument("--require-candidate-pass", type=int, default=1)
    p.add_argument("--require-all-fold-pass", type=int, default=1)
    p.add_argument("--max-corrected-fold-drop", type=int, default=0)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_check(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("summary", {}).get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
