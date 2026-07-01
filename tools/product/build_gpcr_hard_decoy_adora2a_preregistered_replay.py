#!/usr/bin/env python3
"""Replay the ADORA2A rescue through the pre-registered GPCR residual runner.

This is a read-only, claim-locked bridge artifact: it applies the canonical
``gpcr_adora2a_neutral_antagonist_rescue_v1`` prototype spec through the local
runner shadow path on the complete hard-decoy replay rows, then checks that the
runner score reproduces the earlier diagnostic probe score.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools import run_ligand_backmapping_scoring as scoring
from tools.accounting.build_gpcr_residual_prototype_spec import build_payload as build_prototype_spec
from tools.product.build_gpcr_hard_decoy_adora2a_neutral_rescue_probe import (
    BASELINE_BLEND_SCORE_COL,
    DEFAULT_OUT_SCORES_CSV as DEFAULT_PROBE_SCORES_CSV,
    SCORE_COL as PROBE_SCORE_COL,
)
from tools.product.build_gpcr_hard_decoy_current_fit_closure_probe import (
    DEFAULT_LABELS_CSV,
    DEFAULT_SCORES_CSV,
    DEFAULT_SPLIT_CSV,
    _closure_gate,
    _merged_input,
    _metrics,
    _positive_rank_rows,
    _target_metric_rows,
)

ROOT = Path(__file__).resolve().parents[2]

VARIANT = "gpcr_adora2a_neutral_antagonist_rescue_v1"
PACKET_TYPE = "gpcr_hard_decoy_adora2a_preregistered_replay"
SCHEMA_VERSION = "gpcr_hard_decoy_adora2a_preregistered_replay_v1"

DEFAULT_PROTOTYPE_SPEC_JSON = (
    "runs/gpcr_residual_prototype_spec_adora2a_neutral_antagonist_rescue_v1_current.json"
)
DEFAULT_OUT_SCORES_CSV = "runs/gpcr_hard_decoy_adora2a_preregistered_replay_scores_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_adora2a_preregistered_replay_current.md"

SCORE_COL = "binding_score_composite_v7_adora2a_neutral_antagonist_preregistered_replay"

READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "claim_promotion_allowed": False,
    "router_claim_allowed": False,
    "platform_claim_allowed": False,
}

CLAIM_BOUNDARY = (
    "ADORA2A pre-registered runner replay only. It verifies that the claim-locked "
    "ADORA2A neutral-antagonist rescue rule is present in the canonical GPCR residual "
    "runner path and reproduces the diagnostic probe score on complete local hard-decoy "
    "rows. It is not Phase 3 closure, not an official family-ready suite pass, and not "
    "router/platform promotion evidence."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _display(path_like: str | Path) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)
    return str(path)


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = _resolve(path_like)
    if not path.exists():
        raise FileNotFoundError(str(path))
    return pd.read_csv(path)


def _write_prototype_spec(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = build_prototype_spec(variant=VARIANT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _merge_probe_baseline(df: pd.DataFrame, probe_scores_csv: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    probe_scores = _read_csv(probe_scores_csv)
    required = ["target", "ligand_id", BASELINE_BLEND_SCORE_COL]
    missing = [col for col in required if col not in probe_scores.columns]
    if missing:
        raise ValueError(f"probe scores missing required columns: {missing}")
    keep_cols = [
        col
        for col in [
            "target",
            "ligand_id",
            BASELINE_BLEND_SCORE_COL,
            PROBE_SCORE_COL,
            "adora2a_neutral_antagonist_support",
            "adora2a_basic_amine_intrusion_pressure",
        ]
        if col in probe_scores.columns
    ]
    probe_use = probe_scores[keep_cols].drop_duplicates(["target", "ligand_id"])
    merged = df.merge(probe_use, on=["target", "ligand_id"], how="left", validate="one_to_one")
    baseline_missing = int(merged[BASELINE_BLEND_SCORE_COL].isna().sum())
    return merged, {
        "probe_score_rows": int(len(probe_scores)),
        "probe_score_unique_rows": int(len(probe_use)),
        "baseline_missing_count": baseline_missing,
        "probe_score_col_present": PROBE_SCORE_COL in merged.columns,
    }


def _runner_args(spec_json: str | Path) -> Namespace:
    return Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode="apply",
        residual_prototype_family="gpcr",
        residual_prototype_spec_json=str(_resolve(spec_json)),
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=None,
        residual_prototype_yellow_band_abs_delta_score=None,
        score_reference_scaling_mode="run_local",
    )


def _score_diff_summary(out: pd.DataFrame, runner_score: np.ndarray) -> dict[str, Any]:
    if PROBE_SCORE_COL not in out.columns:
        return {
            "score_matches_probe": False,
            "probe_score_col": PROBE_SCORE_COL,
            "probe_score_present": False,
            "max_abs_score_diff_vs_probe": None,
            "mean_abs_score_diff_vs_probe": None,
        }
    probe_score = pd.to_numeric(out[PROBE_SCORE_COL], errors="coerce").to_numpy(dtype=np.float64)
    finite = np.isfinite(probe_score) & np.isfinite(runner_score)
    if not bool(np.any(finite)):
        max_diff = None
        mean_diff = None
    else:
        diff = np.abs(runner_score[finite] - probe_score[finite])
        max_diff = float(np.max(diff))
        mean_diff = float(np.mean(diff))
    return {
        "score_matches_probe": bool(max_diff is not None and max_diff <= 1.0e-9 and int(np.sum(finite)) == len(out)),
        "probe_score_col": PROBE_SCORE_COL,
        "probe_score_present": True,
        "max_abs_score_diff_vs_probe": max_diff,
        "mean_abs_score_diff_vs_probe": mean_diff,
        "finite_probe_score_count": int(np.sum(finite)),
    }


def build_replay(
    *,
    scores_csv: str | Path = DEFAULT_SCORES_CSV,
    labels_csv: str | Path = DEFAULT_LABELS_CSV,
    split_csv: str | Path = DEFAULT_SPLIT_CSV,
    probe_scores_csv: str | Path = DEFAULT_PROBE_SCORES_CSV,
    prototype_spec_json: str | Path = DEFAULT_PROTOTYPE_SPEC_JSON,
    bootstrap_n: int = 400,
    bootstrap_seed: int = 7,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    spec_payload = _write_prototype_spec(prototype_spec_json)
    df = _merged_input(scores_csv, labels_csv, split_csv, eval_roles=("far_ood_eval",))
    df, merge_summary = _merge_probe_baseline(df, probe_scores_csv)
    if merge_summary["baseline_missing_count"]:
        raise ValueError(
            f"missing {merge_summary['baseline_missing_count']} baseline scores after probe merge"
        )

    zero = pd.Series(np.zeros(len(df), dtype=float), index=df.index)
    out, runner_meta = scoring._apply_residual_prototype_shadow(
        df.copy(),
        _runner_args(prototype_spec_json),
        z_e=zero,
        z_d=zero,
        z_s=zero,
        z_c=zero,
        z_aff=zero,
        z_logp=zero,
        z_rot=zero,
        z_hd=zero,
        z_ha=zero,
        z_std=zero,
    )

    runner_score = pd.to_numeric(
        out["binding_score_composite_v7_residual_shadow"],
        errors="coerce",
    ).to_numpy(dtype=np.float64)
    metrics = _metrics(out, runner_score, bootstrap_n=int(bootstrap_n), bootstrap_seed=int(bootstrap_seed))
    positive_rank_rows = _positive_rank_rows(out, runner_score)
    target_metric_rows = _target_metric_rows(out, runner_score)
    gate_pass = _closure_gate(metrics)
    diff_summary = _score_diff_summary(out, runner_score)
    active_locked = bool(runner_meta.get("shadow_only_active_locked"))
    claim_locked = active_locked and runner_meta.get("status") == "shadow_ready_claim_locked"
    replay_ready = bool(gate_pass and diff_summary["score_matches_probe"] and claim_locked)

    out_scores = out[
        [
            col
            for col in [
                "target",
                "ligand_id",
                "mean_min_distance_A",
                "binding_score_composite_v7",
                BASELINE_BLEND_SCORE_COL,
                "gpcr_adora2a_neutral_antagonist_support",
                "gpcr_adora2a_neutral_antagonist_reward",
                "gpcr_adora2a_basic_amine_intrusion_pressure",
                "gpcr_adora2a_basic_amine_intrusion_penalty",
                "binding_score_composite_v7_residual_shadow",
                "binding_score_composite_v7_residual_active",
            ]
            if col in out.columns
        ]
    ].copy()
    out_scores[SCORE_COL] = runner_score

    payload = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": (
            "gpcr_hard_decoy_adora2a_preregistered_replay_gate_pass_claim_locked"
            if replay_ready
            else "blocked_gpcr_hard_decoy_adora2a_preregistered_replay"
        ),
        "scores_csv": str(_resolve(scores_csv)),
        "labels_csv": str(_resolve(labels_csv)),
        "split_csv": str(_resolve(split_csv)),
        "probe_scores_csv": str(_resolve(probe_scores_csv)),
        "prototype_spec_json": str(_resolve(prototype_spec_json)),
        "prototype_variant": VARIANT,
        "runner_score_col": "binding_score_composite_v7_residual_shadow",
        "score_col": SCORE_COL,
        "baseline_score_col": BASELINE_BLEND_SCORE_COL,
        "rows_eval": int(len(out)),
        "positive_count": int(pd.to_numeric(out["is_binder"], errors="coerce").fillna(0).sum()),
        "pre_registered_runner_replay_complete": bool(replay_ready),
        "canonical_runner_status": runner_meta.get("status"),
        "canonical_runner_shadow_only_active_locked": active_locked,
        "canonical_runner_active_score_col": runner_meta.get("active_score_col"),
        "canonical_runner_linear_rescore_status": runner_meta.get("linear_rescore_status"),
        "canonical_runner_summary": runner_meta,
        "prototype_spec_summary": spec_payload.get("summary", {}),
        "merge_summary": merge_summary,
        "runner_replay_target_heldout": metrics,
        "runner_replay_positive_rank_rows": positive_rank_rows,
        "runner_replay_target_metric_rows": target_metric_rows,
        "runner_replay_worst_positive_rank": max(
            (int(row["positive_target_rank"]) for row in positive_rank_rows),
            default=None,
        ),
        "runner_replay_top20_positive_count": sum(1 for row in positive_rank_rows if row["in_top20"]),
        "runner_replay_lowest_target_pr_auc": min(
            (
                float(row["ranking_pr_auc"])
                for row in target_metric_rows
                if row.get("ranking_pr_auc") is not None and np.isfinite(float(row["ranking_pr_auc"]))
            ),
            default=None,
        ),
        "runner_replay_closure_gate_pass": bool(gate_pass),
        "runner_replay_matches_probe_score": bool(diff_summary["score_matches_probe"]),
        **diff_summary,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this pre-registered runner replay as claim-locked diagnostic evidence only; run the official "
            "Phase 3 family suite and require family-ready, CI-low, top20, decoy-separation, and anchor-margin "
            "gates before any claim promotion."
        ),
        **READ_ONLY_FLAGS,
    }
    return out_scores, payload


def write_outputs(
    scores_out: pd.DataFrame,
    payload: dict[str, Any],
    *,
    out_scores_csv: str | Path,
    out_json: str | Path,
    out_md: str | Path,
) -> None:
    scores_path = _resolve(out_scores_csv)
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    for path in (scores_path, json_path, md_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    scores_out.to_csv(scores_path, index=False)
    payload = dict(payload)
    payload["out_scores_csv"] = str(scores_path)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    metrics = payload.get("runner_replay_target_heldout")
    metrics = metrics if isinstance(metrics, dict) else {}
    lines = [
        "# GPCR Hard-Decoy ADORA2A Pre-Registered Replay",
        "",
        f"- status: `{payload.get('status')}`",
        f"- rows_eval: `{payload.get('rows_eval')}`",
        f"- prototype_variant: `{payload.get('prototype_variant')}`",
        f"- canonical_runner_status: `{payload.get('canonical_runner_status')}`",
        f"- score_matches_probe: `{str(payload.get('score_matches_probe')).lower()}`",
        f"- max_abs_score_diff_vs_probe: `{payload.get('max_abs_score_diff_vs_probe')}`",
        f"- runner_replay_ci_low: `{metrics.get('ranking_pr_auc_ci_low')}`",
        f"- runner_replay_top20_hit_rate: `{metrics.get('top20_hit_rate')}`",
        f"- runner_replay_decoys_above_positive_total: `{metrics.get('target_decoys_above_positive_total')}`",
        f"- runner_replay_anchor_margin_gate: `{str(metrics.get('all_required_targets_anchor_margin_nonnegative')).lower()}`",
        f"- runner_replay_closure_gate_pass: `{str(payload.get('runner_replay_closure_gate_pass')).lower()}`",
        f"- claim_promotion_allowed: `{str(payload.get('claim_promotion_allowed')).lower()}`",
        f"- out_scores_csv: `{scores_path}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-csv", default=DEFAULT_SCORES_CSV)
    parser.add_argument("--labels-csv", default=DEFAULT_LABELS_CSV)
    parser.add_argument("--split-csv", default=DEFAULT_SPLIT_CSV)
    parser.add_argument("--probe-scores-csv", default=DEFAULT_PROBE_SCORES_CSV)
    parser.add_argument("--prototype-spec-json", default=DEFAULT_PROTOTYPE_SPEC_JSON)
    parser.add_argument("--bootstrap-n", type=int, default=400)
    parser.add_argument("--bootstrap-seed", type=int, default=7)
    parser.add_argument("--out-scores-csv", default=DEFAULT_OUT_SCORES_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    scores_out, payload = build_replay(
        scores_csv=args.scores_csv,
        labels_csv=args.labels_csv,
        split_csv=args.split_csv,
        probe_scores_csv=args.probe_scores_csv,
        prototype_spec_json=args.prototype_spec_json,
        bootstrap_n=int(args.bootstrap_n),
        bootstrap_seed=int(args.bootstrap_seed),
    )
    write_outputs(
        scores_out,
        payload,
        out_scores_csv=args.out_scores_csv,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
