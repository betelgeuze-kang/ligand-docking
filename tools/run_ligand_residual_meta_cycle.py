#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_active_learning_cycle as active_cycle


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _load_queue(path: str) -> pd.DataFrame:
    src = str(path).strip()
    if (not src) or (not os.path.exists(src)):
        raise FileNotFoundError(f"ligand queue csv not found: {src}")
    df = pd.read_csv(src)
    if df.empty:
        raise ValueError(f"ligand queue csv is empty: {src}")
    if "target" not in df.columns:
        raise ValueError(f"ligand queue csv missing 'target' column: {src}")
    return df


def _build_priority_targets(df: pd.DataFrame, out_csv: str, topk: int) -> pd.DataFrame:
    work = df.copy()
    if "ligand_id" not in work.columns:
        work["ligand_id"] = "unknown_ligand"
    if "ligand_logp" not in work.columns:
        work["ligand_logp"] = np.nan
    if "ligand_mw" not in work.columns:
        work["ligand_mw"] = np.nan
    if "ligand_rot_bonds" not in work.columns:
        work["ligand_rot_bonds"] = np.nan
    agg = (
        work.groupby("target", as_index=False)
        .agg(
            queue_rows=("target", "size"),
            unique_ligands=("ligand_id", "nunique"),
            logp_std=("ligand_logp", "std"),
            mw_std=("ligand_mw", "std"),
            rot_mean=("ligand_rot_bonds", "mean"),
        )
        .fillna(0.0)
    )
    agg["priority_score"] = (
        agg["unique_ligands"].astype(float)
        + 0.05 * agg["queue_rows"].astype(float)
        + 0.2 * agg["logp_std"].astype(float)
        + 0.01 * agg["mw_std"].astype(float)
        + 0.1 * agg["rot_mean"].astype(float)
    )
    agg = agg.sort_values(["priority_score", "target"], ascending=[False, True]).reset_index(drop=True)
    if int(topk) > 0:
        agg = agg.head(int(topk)).copy()
    _ensure_parent(out_csv)
    agg.to_csv(out_csv, index=False)
    return agg


def _build_proxy_ood_pair(df: pd.DataFrame, out_csv: str) -> pd.DataFrame:
    work = df.copy()
    if "ligand_rot_bonds" not in work.columns:
        work["ligand_rot_bonds"] = 0.0
    if "ligand_logp" not in work.columns:
        work["ligand_logp"] = 0.0
    agg = (
        work.groupby("target", as_index=False)
        .agg(
            paired=("target", "size"),
            ligand_count=("ligand_id", "nunique") if "ligand_id" in work.columns else ("target", "size"),
            rot_mean=("ligand_rot_bonds", "mean"),
            logp_std=("ligand_logp", "std"),
        )
        .fillna(0.0)
    )
    agg["paired"] = 1
    agg["rmsd_aligned_A"] = (
        2.5
        + 0.02 * agg["ligand_count"].astype(float)
        + 0.05 * agg["rot_mean"].astype(float)
        + 0.1 * agg["logp_std"].astype(float)
    )
    agg["reason"] = "ligand_queue_proxy"
    out = agg[["target", "paired", "rmsd_aligned_A", "reason"]].copy()
    _ensure_parent(out_csv)
    out.to_csv(out_csv, index=False)
    return out


def run_cycle(args: argparse.Namespace) -> Dict[str, Any]:
    queue_df = _load_queue(str(args.ligand_queue_csv))
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ligand_residual_meta_cycle_{date_tag}"
    _ensure_parent(f"{out_prefix}_summary.json")

    priority_csv = str(args.priority_targets_csv).strip() or f"{out_prefix}_priority_targets.csv"
    proxy_ood_csv = str(args.ood_pair_csv).strip() or f"{out_prefix}_ood_pair_proxy.csv"
    active_prefix = str(args.active_cycle_out_prefix).strip() or f"{out_prefix}_active_learning"

    priority_df = _build_priority_targets(
        queue_df,
        out_csv=priority_csv,
        topk=int(args.priority_topk),
    )
    proxy_df = _build_proxy_ood_pair(queue_df, out_csv=proxy_ood_csv)

    active_args_argv: List[str] = [
        "--date-tag",
        date_tag,
        "--targets",
        str(args.targets),
        "--out-prefix",
        active_prefix,
        "--ood-pair-csv",
        proxy_ood_csv,
        "--accuracy-external-csv",
        str(args.accuracy_external_csv),
        "--stage2-csv",
        str(args.stage2_csv),
        "--hard-mining-topk",
        str(int(args.hard_mining_topk)),
        "--hard-mining-priority-targets-csv",
        priority_csv,
        "--hard-mining-priority-target-col",
        "target",
        "--hard-mining-priority-bonus",
        str(float(args.priority_bonus)),
        "--curriculum-base-manifest-csv",
        str(args.curriculum_base_manifest_csv),
        "--curriculum-max-targets",
        str(int(args.curriculum_max_targets)),
        "--curriculum-checkpoint-dir",
        str(args.curriculum_checkpoint_dir),
        "--curriculum-out-json",
        str(args.curriculum_out_json),
        "--curriculum-summary-json",
        str(args.curriculum_summary_json),
        "--curriculum-summary-csv",
        str(args.curriculum_summary_csv),
        "--claim-policy-json",
        str(args.claim_policy_json),
        "--claim-strict-summary-json",
        str(args.claim_strict_summary_json),
        "--claim-accuracy-external-csv",
        str(args.claim_accuracy_external_csv),
        "--claim-thermo-input-csv",
        str(args.claim_thermo_input_csv),
        "--claim-kinetics-input-csv",
        str(args.claim_kinetics_input_csv),
        "--claim-out-prefix",
        str(args.claim_out_prefix),
    ]
    if bool(args.skip_curriculum_training):
        active_args_argv.append("--skip-curriculum-training")
    else:
        active_args_argv.append("--no-skip-curriculum-training")
    if bool(args.skip_claim_correction):
        active_args_argv.append("--skip-claim-correction")
    else:
        active_args_argv.append("--no-skip-claim-correction")
    if bool(args.dry_run):
        active_args_argv.append("--dry-run")
    else:
        active_args_argv.append("--no-dry-run")

    active_ns = active_cycle.build_parser().parse_args(active_args_argv)
    active_payload = active_cycle.run_cycle(active_ns)

    ligand_stats = (
        queue_df.groupby("target", as_index=False)
        .agg(
            queue_rows=("target", "size"),
            unique_ligands=("ligand_id", "nunique") if "ligand_id" in queue_df.columns else ("target", "size"),
            ligand_mw_mean=("ligand_mw", "mean") if "ligand_mw" in queue_df.columns else ("target", "size"),
            ligand_logp_mean=("ligand_logp", "mean") if "ligand_logp" in queue_df.columns else ("target", "size"),
        )
        .fillna(0.0)
    )
    ligand_stats_csv = f"{out_prefix}_ligand_target_stats.csv"
    _ensure_parent(ligand_stats_csv)
    ligand_stats.to_csv(ligand_stats_csv, index=False)

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "dry_run": bool(args.dry_run),
        "targets": int(queue_df["target"].nunique()),
        "queue_rows": int(len(queue_df)),
        "unique_ligands": int(queue_df["ligand_id"].nunique()) if "ligand_id" in queue_df.columns else 0,
        "priority_targets_count": int(len(priority_df)),
        "active_learning_pass": bool(active_payload.get("pass", False)),
        "active_learning_summary": active_payload.get("summary", {}),
        "artifacts": {
            "ligand_queue_csv": str(args.ligand_queue_csv),
            "priority_targets_csv": priority_csv,
            "proxy_ood_pair_csv": proxy_ood_csv,
            "ligand_target_stats_csv": ligand_stats_csv,
            "active_learning_summary_json": f"{active_prefix}_summary.json",
        },
    }

    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    lines = [
        "# Ligand Residual + Meta Cycle",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- dry_run: {summary['dry_run']}",
        f"- targets: {summary['targets']}",
        f"- queue_rows: {summary['queue_rows']}",
        f"- unique_ligands: {summary['unique_ligands']}",
        f"- priority_targets_count: {summary['priority_targets_count']}",
        f"- active_learning_pass: {summary['active_learning_pass']}",
        "",
        "## Artifacts",
        f"- priority_targets_csv: `{priority_csv}`",
        f"- proxy_ood_pair_csv: `{proxy_ood_csv}`",
        f"- ligand_target_stats_csv: `{ligand_stats_csv}`",
        f"- active_learning_summary_json: `{active_prefix}_summary.json`",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "Run ligand-aware residual/meta learning cycle. "
            "Build priority targets + proxy OOD pairs from ligand queue and invoke active-learning cycle."
        )
    )
    p.add_argument("--ligand-queue-csv", type=str, required=True)
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--out-prefix", type=str, default=f"runs/ligand_residual_meta_cycle_{stamp}")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)

    p.add_argument("--priority-topk", type=int, default=4)
    p.add_argument("--priority-bonus", type=float, default=1.5)
    p.add_argument("--priority-targets-csv", type=str, default="")
    p.add_argument("--ood-pair-csv", type=str, default="")

    p.add_argument("--hard-mining-topk", type=int, default=4)
    p.add_argument(
        "--curriculum-base-manifest-csv",
        type=str,
        default="runs/distilled_residual_manifest_repaired_fp32_cap100.csv",
    )
    p.add_argument("--curriculum-max-targets", type=int, default=10)
    p.add_argument("--curriculum-checkpoint-dir", type=str, default="models/curriculum_ligand_active")
    p.add_argument("--curriculum-out-json", type=str, default=f"runs/bigdata_curriculum_ligand_active_{stamp}.json")
    p.add_argument("--curriculum-summary-json", type=str, default=f"runs/train_curriculum_ligand_active_{stamp}.json")
    p.add_argument("--curriculum-summary-csv", type=str, default=f"runs/train_curriculum_ligand_active_{stamp}.csv")

    p.add_argument("--skip-curriculum-training", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--skip-claim-correction", action=argparse.BooleanOptionalAction, default=True)

    p.add_argument("--accuracy-external-csv", type=str, default="")
    p.add_argument("--stage2-csv", type=str, default="")
    p.add_argument("--claim-policy-json", type=str, default="config/allatom_equivalence_acceptance_v1_2026-02-17.json")
    p.add_argument("--claim-strict-summary-json", type=str, default="")
    p.add_argument("--claim-accuracy-external-csv", type=str, default="")
    p.add_argument("--claim-thermo-input-csv", type=str, default="")
    p.add_argument("--claim-kinetics-input-csv", type=str, default="")
    p.add_argument("--claim-out-prefix", type=str, default=f"runs/claim_metric_correction_loop_ligand_active_{stamp}")
    p.add_argument("--active-cycle-out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_cycle(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
