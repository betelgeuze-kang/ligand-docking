#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

from core.definitions import ResearchConstants
from tools.build_hard_mining_target_weights import build_hard_mining_target_weights
from tools import run_bigdata_curriculum_training as curriculum_runner
from tools import run_claim_metric_correction_loop as claim_loop_runner


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _maybe_add(argv: List[str], key: str, value: str) -> None:
    v = str(value).strip()
    if v:
        argv.extend([key, v])


def _parse_targets(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    uniq: List[str] = []
    seen = set()
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq


def run_cycle(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/active_learning_cycle_{date_tag}"
    _ensure_parent(f"{out_prefix}_summary.json")
    selected_targets = _parse_targets(str(args.targets))

    hard_weights_csv = str(args.hard_mining_out_target_weights_csv).strip() or f"{out_prefix}_target_weights.csv"
    hard_scores_csv = str(args.hard_mining_out_score_csv).strip() or f"{out_prefix}_hard_scores.csv"
    hard_summary_json = str(args.hard_mining_out_summary_json).strip() or f"{out_prefix}_hard_summary.json"

    hard_payload = build_hard_mining_target_weights(
        targets=str(args.targets),
        ood_pair_csv=str(args.ood_pair_csv),
        accuracy_external_csv=str(args.accuracy_external_csv),
        stage2_csv=str(args.stage2_csv),
        topk=int(args.hard_mining_topk),
        base_weight=float(args.base_weight),
        max_weight=float(args.hard_mining_max_weight),
        weight_scale=float(args.hard_mining_weight_scale),
        unpaired_boost=float(args.hard_mining_unpaired_boost),
        ood_rmsd_threshold=float(args.hard_mining_ood_rmsd_threshold),
        native_rmsd_threshold=float(args.hard_mining_native_rmsd_threshold),
        uncertainty_threshold=float(args.hard_mining_uncertainty_threshold),
        fallback_ratio_threshold=float(args.hard_mining_fallback_ratio_threshold),
        physics_violations_threshold=float(args.hard_mining_physics_violations_threshold),
        uncertainty_weight=float(args.hard_mining_uncertainty_weight),
        fallback_weight=float(args.hard_mining_fallback_weight),
        physics_weight=float(args.hard_mining_physics_weight),
        out_target_weights_csv=hard_weights_csv,
        out_score_csv=hard_scores_csv,
        out_summary_json=hard_summary_json,
        priority_targets_csv=str(args.hard_mining_priority_targets_csv),
        priority_target_col=str(args.hard_mining_priority_target_col),
        priority_bonus=float(args.hard_mining_priority_bonus),
    )

    curriculum_payload: Optional[Dict[str, Any]] = None
    curriculum_cmd: List[str] = [
        "--targets",
        str(args.targets),
        "--base-manifest-csv",
        str(args.curriculum_base_manifest_csv),
        "--out-merged-manifest-csv",
        str(args.curriculum_out_merged_manifest_csv),
        "--out-merged-summary-json",
        str(args.curriculum_out_merged_summary_json),
        "--target-weights-csv",
        hard_weights_csv,
        "--run-tag",
        str(args.curriculum_run_tag or f"active_learning_{date_tag}"),
        "--checkpoint-dir",
        str(args.curriculum_checkpoint_dir),
        "--curriculum-summary-json",
        str(args.curriculum_summary_json),
        "--curriculum-summary-csv",
        str(args.curriculum_summary_csv),
        "--out-json",
        str(args.curriculum_out_json),
    ]
    _maybe_add(curriculum_cmd, "--hardcase-manifest-csv", str(args.curriculum_hardcase_manifest_csv))
    curriculum_max_targets = int(args.curriculum_max_targets)
    if curriculum_max_targets <= 0 and str(args.targets).strip().lower() != "all":
        curriculum_max_targets = max(1, len(selected_targets))
    if curriculum_max_targets > 0:
        curriculum_cmd.extend(["--max-targets", str(int(curriculum_max_targets))])
    if bool(args.curriculum_skip_manifest_build):
        curriculum_cmd.append("--skip-manifest-build")
    if bool(args.curriculum_hp_search):
        curriculum_cmd.append("--hp-search")

    if (not bool(args.skip_curriculum_training)) and (not bool(args.dry_run)):
        curriculum_ns = curriculum_runner.build_parser().parse_args(curriculum_cmd)
        curriculum_payload = curriculum_runner.run_bigdata_curriculum(curriculum_ns)

    claim_payload: Optional[Dict[str, Any]] = None
    claim_cmd: List[str] = [
        "--policy-json",
        str(args.claim_policy_json),
        "--strict-summary-json",
        str(args.claim_strict_summary_json),
        "--accuracy-external-csv",
        str(args.claim_accuracy_external_csv),
        "--thermo-input-csv",
        str(args.claim_thermo_input_csv),
        "--kinetics-input-csv",
        str(args.claim_kinetics_input_csv),
        "--max-iters",
        str(int(args.claim_max_iters)),
        "--target-margin",
        str(float(args.claim_target_margin)),
        "--damping",
        str(float(args.claim_damping)),
        "--out-prefix",
        str(args.claim_out_prefix),
    ]
    _maybe_add(claim_cmd, "--experiment-input-csv", str(args.claim_experiment_input_csv))
    if bool(args.claim_enforce_complete):
        claim_cmd.append("--enforce-complete-claim")

    run_claim = not bool(args.skip_claim_correction)
    if run_claim and (not bool(args.dry_run)):
        claim_ns = claim_loop_runner.build_parser().parse_args(claim_cmd)
        claim_payload = claim_loop_runner.run_loop(claim_ns)

    pass_curriculum = bool(args.skip_curriculum_training or args.dry_run or (curriculum_payload is not None))
    claim_summary = (
        claim_payload.get("summary", {})
        if isinstance(claim_payload, dict) and isinstance(claim_payload.get("summary"), dict)
        else {}
    )
    pass_claim = bool((not run_claim) or args.dry_run or (claim_payload is not None))
    summary = {
        "hard_mining_selected_targets_count": int(
            hard_payload.get("summary", {}).get("selected_targets_count", 0)
            if isinstance(hard_payload.get("summary"), dict)
            else 0
        ),
        "hard_mining_selected_targets": (
            hard_payload.get("summary", {}).get("selected_targets", [])
            if isinstance(hard_payload.get("summary"), dict)
            else []
        ),
        "hard_mining_priority_targets_matched": int(
            hard_payload.get("summary", {}).get("priority_targets_matched", 0)
            if isinstance(hard_payload.get("summary"), dict)
            else 0
        ),
        "curriculum_executed": bool((not args.skip_curriculum_training) and (not args.dry_run)),
        "curriculum_pass": bool(pass_curriculum),
        "claim_executed": bool(run_claim and (not args.dry_run)),
        "claim_pass": bool(pass_claim),
        "claim_ready_for_allatom": bool(claim_summary.get("claim_ready_for_allatom", False)) if claim_summary else None,
        "claim_failed_metrics_after_runner": (
            int(claim_summary.get("claim_failed_metrics_after_runner", -1)) if claim_summary else None
        ),
    }
    passed = bool(pass_curriculum and pass_claim)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "dry_run": bool(args.dry_run),
        "summary": summary,
        "pass": passed,
        "inputs": {
            "targets": str(args.targets),
            "ood_pair_csv": str(args.ood_pair_csv),
            "accuracy_external_csv": str(args.accuracy_external_csv),
            "stage2_csv": str(args.stage2_csv),
            "hard_mining_priority_targets_csv": str(args.hard_mining_priority_targets_csv),
            "hard_mining_priority_bonus": float(args.hard_mining_priority_bonus),
            "skip_curriculum_training": bool(args.skip_curriculum_training),
            "skip_claim_correction": bool(args.skip_claim_correction),
        },
        "commands": {
            "curriculum": curriculum_cmd,
            "claim_correction": claim_cmd if run_claim else [],
        },
        "artifacts": {
            "hard_mining_target_weights_csv": hard_weights_csv,
            "hard_mining_score_csv": hard_scores_csv,
            "hard_mining_summary_json": hard_summary_json,
            "curriculum_out_json": str(args.curriculum_out_json),
            "claim_out_prefix": str(args.claim_out_prefix),
            "summary_json": f"{out_prefix}_summary.json",
            "summary_md": f"{out_prefix}_summary.md",
        },
    }

    with open(f"{out_prefix}_summary.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = [
        "# Active Learning Cycle",
        "",
        f"- generated_at: {payload['generated_at_local']}",
        f"- dry_run: {payload['dry_run']}",
        f"- pass: {payload['pass']}",
        f"- hard_mining_selected_targets_count: {summary['hard_mining_selected_targets_count']}",
        f"- hard_mining_selected_targets: {summary['hard_mining_selected_targets']}",
        f"- hard_mining_priority_targets_matched: {summary['hard_mining_priority_targets_matched']}",
        f"- curriculum_executed: {summary['curriculum_executed']}",
        f"- curriculum_pass: {summary['curriculum_pass']}",
        f"- claim_executed: {summary['claim_executed']}",
        f"- claim_pass: {summary['claim_pass']}",
        f"- claim_ready_for_allatom: {summary['claim_ready_for_allatom']}",
        f"- claim_failed_metrics_after_runner: {summary['claim_failed_metrics_after_runner']}",
        "",
        "## Artifacts",
        f"- summary_json: {out_prefix}_summary.json",
        f"- hard_mining_target_weights_csv: {hard_weights_csv}",
        f"- hard_mining_score_csv: {hard_scores_csv}",
        f"- curriculum_out_json: {args.curriculum_out_json}",
        f"- claim_out_prefix: {args.claim_out_prefix}",
    ]
    with open(f"{out_prefix}_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run one active-learning cycle: hard-mining target weighting -> bigdata curriculum retrain -> "
            "optional claim correction loop."
        )
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--out-prefix", type=str, default=f"runs/active_learning_cycle_{stamp}")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--ood-pair-csv", type=str, required=True)
    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--stage2-csv", type=str, default="")
    p.add_argument("--base-weight", type=float, default=1.0)
    p.add_argument("--hard-mining-topk", type=int, default=4)
    p.add_argument("--hard-mining-max-weight", type=float, default=4.0)
    p.add_argument("--hard-mining-weight-scale", type=float, default=1.0)
    p.add_argument("--hard-mining-unpaired-boost", type=float, default=2.0)
    p.add_argument("--hard-mining-ood-rmsd-threshold", type=float, default=6.0)
    p.add_argument("--hard-mining-native-rmsd-threshold", type=float, default=0.5)
    p.add_argument("--hard-mining-uncertainty-threshold", type=float, default=0.3)
    p.add_argument("--hard-mining-fallback-ratio-threshold", type=float, default=0.05)
    p.add_argument("--hard-mining-physics-violations-threshold", type=float, default=0.0)
    p.add_argument("--hard-mining-uncertainty-weight", type=float, default=0.75)
    p.add_argument("--hard-mining-fallback-weight", type=float, default=0.50)
    p.add_argument("--hard-mining-physics-weight", type=float, default=0.50)
    p.add_argument("--hard-mining-priority-targets-csv", type=str, default="")
    p.add_argument("--hard-mining-priority-target-col", type=str, default="target")
    p.add_argument("--hard-mining-priority-bonus", type=float, default=0.0)
    p.add_argument("--hard-mining-out-target-weights-csv", type=str, default="")
    p.add_argument("--hard-mining-out-score-csv", type=str, default="")
    p.add_argument("--hard-mining-out-summary-json", type=str, default="")

    p.add_argument("--skip-curriculum-training", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--curriculum-base-manifest-csv", type=str, default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv")
    p.add_argument("--curriculum-hardcase-manifest-csv", type=str, default="")
    p.add_argument("--curriculum-skip-manifest-build", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--curriculum-hp-search", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--curriculum-max-targets", type=int, default=0)
    p.add_argument("--curriculum-run-tag", type=str, default="")
    p.add_argument("--curriculum-checkpoint-dir", type=str, default="models/curriculum_active_learning")
    p.add_argument("--curriculum-out-merged-manifest-csv", type=str, default=f"runs/distilled_residual_manifest_active_learning_{stamp}.csv")
    p.add_argument("--curriculum-out-merged-summary-json", type=str, default=f"runs/distilled_residual_active_learning_summary_{stamp}.json")
    p.add_argument("--curriculum-summary-json", type=str, default=f"runs/train_curriculum_active_learning_{stamp}.json")
    p.add_argument("--curriculum-summary-csv", type=str, default=f"runs/train_curriculum_active_learning_{stamp}.csv")
    p.add_argument("--curriculum-out-json", type=str, default=f"runs/bigdata_curriculum_active_learning_{stamp}.json")

    p.add_argument("--skip-claim-correction", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--claim-policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--claim-strict-summary-json", type=str, default="")
    p.add_argument("--claim-accuracy-external-csv", type=str, default="")
    p.add_argument("--claim-thermo-input-csv", type=str, default="")
    p.add_argument("--claim-kinetics-input-csv", type=str, default="")
    p.add_argument("--claim-experiment-input-csv", type=str, default="")
    p.add_argument("--claim-max-iters", type=int, default=10)
    p.add_argument("--claim-target-margin", type=float, default=0.9)
    p.add_argument("--claim-damping", type=float, default=0.75)
    p.add_argument("--claim-enforce-complete", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--claim-out-prefix", type=str, default=f"runs/claim_metric_correction_loop_active_learning_{stamp}")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_cycle(args)
    print(json.dumps(payload.get("summary", {}), indent=2, ensure_ascii=False))
    print(f"Wrote JSON: {args.out_prefix}_summary.json")
    print(f"Wrote MD: {args.out_prefix}_summary.md")
    if not bool(payload.get("pass", False)):
        sys.exit(2)


if __name__ == "__main__":
    main()
