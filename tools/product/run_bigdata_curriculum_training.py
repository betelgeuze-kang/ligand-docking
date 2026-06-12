#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence

from tools.build_bigdata_residual_manifest import build_bigdata_residual_manifest
from tools.build_hard_mining_target_weights import build_hard_mining_target_weights
from train.train_pipeline import run_training_pipeline


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _default_date_tag() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d")


def run_bigdata_curriculum(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag or _default_date_tag())
    run_tag = str(args.run_tag or f"bigdata_curriculum_{date_tag}")

    manifest_path = str(args.out_merged_manifest_csv)
    manifest_summary_path = str(args.out_merged_summary_json)
    effective_target_weights_csv = str(args.target_weights_csv).strip() or None

    manifest_summary: Optional[Dict[str, Any]] = None
    hard_mining_summary: Optional[Dict[str, Any]] = None
    if bool(args.auto_hard_mining):
        ood_pair_csv = str(args.hard_mining_ood_pair_csv).strip()
        if not ood_pair_csv:
            raise ValueError("--hard-mining-ood-pair-csv is required when --auto-hard-mining is enabled")
        hard_mining_summary = build_hard_mining_target_weights(
            targets=str(args.targets),
            ood_pair_csv=ood_pair_csv,
            accuracy_external_csv=str(args.hard_mining_accuracy_external_csv),
            stage2_csv=str(args.hard_mining_stage2_csv),
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
            out_target_weights_csv=str(args.hard_mining_out_target_weights_csv),
            out_score_csv=str(args.hard_mining_out_score_csv),
            out_summary_json=str(args.hard_mining_out_summary_json),
        )
        if not effective_target_weights_csv:
            effective_target_weights_csv = str(args.hard_mining_out_target_weights_csv)

    if not bool(args.skip_manifest_build):
        manifest_summary = build_bigdata_residual_manifest(
            targets=str(args.targets),
            base_manifest_csv=str(args.base_manifest_csv),
            hardcase_manifest_csv=(str(args.hardcase_manifest_csv).strip() or None),
            hardcase_h5_glob=str(args.hardcase_h5_glob),
            hardcase_out_dir=str(args.hardcase_out_dir),
            hardcase_out_manifest_csv=str(args.hardcase_out_manifest_csv),
            hardcase_out_summary_json=str(args.hardcase_out_summary_json),
            hardcase_float_dtype=str(args.hardcase_float_dtype),
            hardcase_keep_coords=bool(args.hardcase_keep_coords),
            hardcase_min_quality=args.hardcase_min_quality,
            hardcase_max_samples_per_file=args.hardcase_max_samples_per_file,
            hardcase_repair_zero_residual=bool(args.hardcase_repair_zero_residual),
            hardcase_zero_residual_atol=float(args.hardcase_zero_residual_atol),
            hardcase_repair_device=str(args.hardcase_repair_device),
            hardcase_reference_cutoff=float(args.hardcase_reference_cutoff),
            hardcase_reference_max_neighbors=int(args.hardcase_reference_max_neighbors),
            hardcase_reference_force_cap=(
                None if float(args.hardcase_reference_force_cap) <= 0.0 else float(args.hardcase_reference_force_cap)
            ),
            base_weight=float(args.base_weight),
            hardcase_weight=float(args.hardcase_weight),
            length_weight_beta=float(args.length_weight_beta),
            length_reference_n_res=float(args.length_reference_n_res),
            target_weights_csv=effective_target_weights_csv,
            bead_consistency_policy=str(args.bead_consistency_policy),
            min_sampling_weight=float(args.min_sampling_weight),
            skip_missing_output_npz=bool(args.skip_missing_output_npz),
            out_manifest_csv=manifest_path,
            out_summary_json=manifest_summary_path,
        )

    training_payload = run_training_pipeline(
        target="all",
        use_hp_search=bool(args.hp_search),
        schedule=str(args.schedule),
        seed=int(args.seed),
        max_targets=args.max_targets,
        data_source="distilled",
        distilled_manifest=manifest_path,
        distilled_split_col=str(args.distilled_split_col),
        distilled_min_quality=args.distilled_min_quality,
        distilled_max_samples_per_shard=args.distilled_max_samples_per_shard,
        distilled_sample_weight_col=str(args.distilled_sample_weight_col),
        distilled_default_shard_weight=float(args.distilled_default_shard_weight),
        distilled_quality_weight_alpha=float(args.distilled_quality_weight_alpha),
        distilled_min_sampling_weight=float(args.distilled_min_sampling_weight),
        distilled_use_weighted_sampler=bool(args.distilled_use_weighted_sampler),
        distilled_weighted_sampler_replacement=bool(args.distilled_weighted_sampler_replacement),
        initial_checkpoint=str(args.initial_checkpoint or ""),
        checkpoint_strict=bool(args.checkpoint_strict),
        carry_over_checkpoint=bool(args.carry_over_checkpoint),
        checkpoint_dir=str(args.checkpoint_dir),
        early_stop_patience=int(args.early_stop_patience),
        curriculum_summary_json=str(args.curriculum_summary_json or ""),
        curriculum_summary_csv=str(args.curriculum_summary_csv or ""),
        run_tag=run_tag,
    )

    payload = {
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "date_tag": date_tag,
        "run_tag": run_tag,
        "manifest_built": (manifest_summary is not None),
        "hard_mining_enabled": bool(args.auto_hard_mining),
        "hard_mining_summary": hard_mining_summary,
        "manifest_path": manifest_path,
        "manifest_summary_path": manifest_summary_path,
        "manifest_summary": manifest_summary,
        "training": training_payload,
        "artifacts": {
            "manifest_csv": manifest_path,
            "manifest_summary_json": manifest_summary_path,
            "target_weights_csv": (effective_target_weights_csv or ""),
            "hard_mining_target_weights_csv": str(args.hard_mining_out_target_weights_csv or ""),
            "hard_mining_score_csv": str(args.hard_mining_out_score_csv or ""),
            "hard_mining_summary_json": str(args.hard_mining_out_summary_json or ""),
            "curriculum_summary_json": str(args.curriculum_summary_json or ""),
            "curriculum_summary_csv": str(args.curriculum_summary_csv or ""),
        },
    }

    out_json = str(args.out_json)
    if out_json:
        _ensure_parent(out_json)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run bigdata residual manifest build and all-target curriculum training in one command."
    )
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--run-tag", type=str, default="")

    # Manifest build options
    p.add_argument("--skip-manifest-build", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--base-manifest-csv", type=str, default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv")
    p.add_argument("--hardcase-manifest-csv", type=str, default="")
    p.add_argument("--hardcase-h5-glob", type=str, default="data/residual_hardcases_2026-02-15/*_airouter_*_data.h5")
    p.add_argument("--hardcase-out-dir", type=str, default="data/distilled_residual_hardcases")
    p.add_argument("--hardcase-out-manifest-csv", type=str, default="runs/distilled_residual_manifest_hardcases.csv")
    p.add_argument("--hardcase-out-summary-json", type=str, default="runs/distilled_residual_summary_hardcases.json")
    p.add_argument("--hardcase-float-dtype", type=str, default="float32", choices=["float16", "float32"])
    p.add_argument("--hardcase-keep-coords", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--hardcase-min-quality", type=float, default=None)
    p.add_argument("--hardcase-max-samples-per-file", type=int, default=None)
    p.add_argument("--hardcase-repair-zero-residual", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--hardcase-zero-residual-atol", type=float, default=1e-8)
    p.add_argument("--hardcase-repair-device", type=str, default="cuda")
    p.add_argument("--hardcase-reference-cutoff", type=float, default=14.0)
    p.add_argument("--hardcase-reference-max-neighbors", type=int, default=160)
    p.add_argument("--hardcase-reference-force-cap", type=float, default=100.0)
    p.add_argument("--base-weight", type=float, default=1.0)
    p.add_argument("--hardcase-weight", type=float, default=3.0)
    p.add_argument("--length-weight-beta", type=float, default=0.0)
    p.add_argument("--length-reference-n-res", type=float, default=40.0)
    p.add_argument("--target-weights-csv", type=str, default="")
    p.add_argument("--auto-hard-mining", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--hard-mining-ood-pair-csv", type=str, default="")
    p.add_argument("--hard-mining-accuracy-external-csv", type=str, default="")
    p.add_argument("--hard-mining-stage2-csv", type=str, default="")
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
    p.add_argument("--hard-mining-out-target-weights-csv", type=str, default="runs/hard_mining_target_weights_curriculum.csv")
    p.add_argument("--hard-mining-out-score-csv", type=str, default="runs/hard_mining_scores_curriculum.csv")
    p.add_argument("--hard-mining-out-summary-json", type=str, default="runs/hard_mining_summary_curriculum.json")
    p.add_argument("--bead-consistency-policy", type=str, default="max_atoms", choices=["none", "max_atoms", "min_atoms"])
    p.add_argument("--min-sampling-weight", type=float, default=1e-6)
    p.add_argument("--skip-missing-output-npz", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-merged-manifest-csv", type=str, default="runs/distilled_residual_manifest_bigdata.csv")
    p.add_argument("--out-merged-summary-json", type=str, default="runs/distilled_residual_bigdata_summary.json")

    # Training options
    p.add_argument(
        "--schedule",
        type=str,
        default="size_ascending",
        choices=["fold_balanced", "round_robin", "alphabetical", "size_ascending", "size_descending", "defined"],
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-targets", type=int, default=None)
    p.add_argument("--hp-search", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--distilled-split-col", type=str, default="split")
    p.add_argument("--distilled-min-quality", type=float, default=None)
    p.add_argument("--distilled-max-samples-per-shard", type=int, default=None)
    p.add_argument("--distilled-sample-weight-col", type=str, default="sampling_weight")
    p.add_argument("--distilled-default-shard-weight", type=float, default=1.0)
    p.add_argument("--distilled-quality-weight-alpha", type=float, default=0.0)
    p.add_argument("--distilled-min-sampling-weight", type=float, default=1e-6)
    p.add_argument("--distilled-use-weighted-sampler", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--distilled-weighted-sampler-replacement", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--initial-checkpoint", type=str, default="")
    p.add_argument("--checkpoint-strict", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--carry-over-checkpoint", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--checkpoint-dir", type=str, default="models/curriculum")
    p.add_argument("--early-stop-patience", type=int, default=10)
    p.add_argument("--curriculum-summary-json", type=str, default="")
    p.add_argument("--curriculum-summary-csv", type=str, default="")
    p.add_argument("--out-json", type=str, default="runs/bigdata_curriculum_training_summary.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_bigdata_curriculum(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
