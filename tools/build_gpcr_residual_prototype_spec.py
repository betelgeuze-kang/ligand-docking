#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/gpcr_residual_prototype_spec_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_prototype_spec_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_prototype_spec_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _feature_rows(variant: str) -> list[dict[str, Any]]:
    rows = [
        {
            "feature_name": "ligand_h_donors",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "High donor counts are over-rewarded in v7 relative to geometry/contact evidence.",
        },
        {
            "feature_name": "ligand_h_acceptors",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "Acceptor-rich hard decoys rise too high under the current GPCR composite.",
        },
        {
            "feature_name": "ligand_rot_bonds",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "Flexible decoys benefit from current prior weights and need structural support checks.",
        },
        {
            "feature_name": "ligand_logp",
            "role": "calibration_penalty",
            "direction": "penalize_low_logp_when_geometry_is_weak",
            "rationale": "Low-logP priors are currently rewarded through run-level scaling and shift under larger libraries.",
        },
        {
            "feature_name": "ligand_affinity_hint",
            "role": "prior_penalty",
            "direction": "penalize_when_hint_disagrees_with_md",
            "rationale": "Affinity hints need a mismatch penalty when contact/distance evidence is weak.",
        },
        {
            "feature_name": "binding_energy_proxy",
            "role": "support_signal",
            "direction": "reward_only_when_consistent",
            "rationale": "Energy should support positive correction but not dominate when other structural signals are weak.",
        },
        {
            "feature_name": "contact_fraction",
            "role": "support_signal",
            "direction": "reward_when_high",
            "rationale": "Low-contact decoys are slipping through; contact should anchor positive correction.",
        },
        {
            "feature_name": "stability_score",
            "role": "support_signal",
            "direction": "reward_when_high",
            "rationale": "The residual should trust stable trajectories more than prior-favorable but unstable ones.",
        },
        {
            "feature_name": "mean_min_distance_A",
            "role": "guardrail_signal",
            "direction": "penalize_when_far",
            "rationale": "Current GPCR v7 gives distance zero weight, which allows far-but-prior-like decoys through.",
        },
        {
            "feature_name": "prior_structure_mismatch",
            "role": "interaction_term",
            "direction": "penalize_when_high",
            "rationale": "Explicitly capture donor/acceptor/rotor richness without matching contact and distance support.",
        },
    ]
    if variant == "narrow_v2":
        for row in rows:
            if row["feature_name"] in {
                "ligand_h_donors",
                "ligand_h_acceptors",
                "ligand_rot_bonds",
                "ligand_logp",
                "ligand_affinity_hint",
            }:
                row["rationale"] += " Narrow-v2 only activates these behind explicit distance/contact mismatch gates."
    return rows


def build_payload(*, variant: str = "current") -> dict[str, Any]:
    feature_rows = _feature_rows(variant)
    constraints = {
        "max_abs_delta_score": 1.5,
        "yellow_band_abs_delta_score": 0.75,
        "preserve_top2_binders": True,
        "require_energy_contact_support_for_positive_delta": True,
        "fallback_on_ood": True,
        "fallback_on_low_confidence": True,
        "reference_scaling_mode": "fixed_family_reference",
    }
    tuning: dict[str, Any] = {"variant": "current"}
    interactions = [
        "high_donor_acceptor_rotor_with_weak_contact",
        "high_donor_acceptor_rotor_with_far_distance",
        "low_logp_with_weak_energy",
        "high_affinity_hint_with_weak_md_evidence",
    ]
    next_step = (
        "Run equal-size GPCR A/B with shadow residual telemetry, then use the comparison artifacts "
        "to decide whether an apply-mode experiment is safe for the 100k commercialization path."
    )

    if variant == "narrow_v2":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.75,
            "yellow_band_abs_delta_score": 0.35,
        }
        tuning = {
            "variant": "narrow_v2",
            "prior_weight_h_donors": 0.22,
            "prior_weight_h_acceptors": 0.20,
            "prior_weight_rot_bonds": 0.10,
            "prior_weight_neg_logp": 0.06,
            "weakness_weight_distance": 0.80,
            "weakness_weight_neg_contact": 0.70,
            "weakness_weight_neg_stability": 0.25,
            "weakness_weight_energy": 0.15,
            "support_weight_neg_energy": 0.20,
            "support_weight_contact": 0.35,
            "support_weight_stability": 0.10,
            "support_weight_neg_distance": 0.35,
            "interaction_bias": 0.20,
            "affinity_mismatch_weight": 0.12,
            "affinity_interaction_bias": 0.15,
            "support_penalty_weight": 0.08,
            "min_prior_pressure_for_delta": 0.85,
            "min_structural_weakness_for_delta": 0.90,
            "max_structural_support_for_delta": 0.20,
            "min_raw_delta_for_activation": 0.25,
            "require_distance_above_z": 0.35,
            "require_contact_below_z": -0.20,
        }
        interactions = [
            "prior_pressure_only_when_distance_is_far",
            "prior_pressure_only_when_contact_is_weak",
            "affinity_hint_only_when_md_is_weak_and_support_is_low",
        ]
        next_step = (
            "Run a locked-decoy GPCR shadow A/B with narrow-v2 gating, verify PR-AUC no longer regresses, "
            "then run locked-decoy apply only if the shadow telemetry remains claim-safe."
        )
    elif variant == "chembl50_v3":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.50,
            "yellow_band_abs_delta_score": 0.20,
        }
        tuning = {
            "variant": "chembl50_v3",
            "prior_weight_h_donors": 0.18,
            "prior_weight_h_acceptors": 0.16,
            "prior_weight_rot_bonds": 0.08,
            "prior_weight_neg_logp": 0.04,
            "weakness_weight_distance": 0.85,
            "weakness_weight_neg_contact": 0.78,
            "weakness_weight_neg_stability": 0.18,
            "weakness_weight_energy": 0.10,
            "support_weight_neg_energy": 0.15,
            "support_weight_contact": 0.30,
            "support_weight_stability": 0.08,
            "support_weight_neg_distance": 0.40,
            "interaction_bias": 0.12,
            "affinity_mismatch_weight": 0.08,
            "affinity_interaction_bias": 0.10,
            "support_penalty_weight": 0.05,
            "min_prior_pressure_for_delta": 0.92,
            "min_structural_weakness_for_delta": 0.95,
            "max_structural_support_for_delta": 0.12,
            "min_raw_delta_for_activation": 0.30,
            "require_distance_above_z": 0.45,
            "require_contact_below_z": -0.30,
            "chembl50_abstain_on_borderline_support": True,
        }
        interactions = [
            "chembl50_prior_pressure_only_when_distance_is_far",
            "chembl50_prior_pressure_only_when_contact_is_weak",
            "chembl50_abstain_when_support_is_borderline",
        ]
        next_step = (
            "Use this chembl50-focused v3 as the next locked-decoy shadow candidate. It should only fire on stronger "
            "distance/contact mismatch and abstain on borderline support before any apply-mode retry."
        )
    elif variant == "chembl50_v4":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.35,
            "yellow_band_abs_delta_score": 0.12,
        }
        tuning = {
            "variant": "chembl50_v4",
            "prior_weight_h_donors": 0.14,
            "prior_weight_h_acceptors": 0.12,
            "prior_weight_rot_bonds": 0.06,
            "prior_weight_neg_logp": 0.03,
            "weakness_weight_distance": 0.90,
            "weakness_weight_neg_contact": 0.84,
            "weakness_weight_neg_stability": 0.14,
            "weakness_weight_energy": 0.08,
            "support_weight_neg_energy": 0.12,
            "support_weight_contact": 0.26,
            "support_weight_stability": 0.06,
            "support_weight_neg_distance": 0.42,
            "interaction_bias": 0.08,
            "affinity_mismatch_weight": 0.06,
            "affinity_interaction_bias": 0.08,
            "support_penalty_weight": 0.03,
            "min_prior_pressure_for_delta": 0.96,
            "min_structural_weakness_for_delta": 0.98,
            "max_structural_support_for_delta": 0.08,
            "min_raw_delta_for_activation": 0.38,
            "require_distance_above_z": 0.55,
            "require_contact_below_z": -0.35,
            "chembl50_abstain_on_borderline_support": True,
            "core_guard_abstain_on_small_margin": True,
        }
        interactions = [
            "chembl50_v4_prior_pressure_only_when_distance_is_far",
            "chembl50_v4_prior_pressure_only_when_contact_is_weak",
            "chembl50_v4_abstain_when_support_is_borderline_or_core_like",
        ]
        next_step = (
            "Use chembl50_v4 as a narrower core-guard shadow candidate. The goal is to preserve the chembl50 OOD gain "
            "while shrinking active deltas enough that gpcr_core_full no longer regresses before any apply-mode retry."
        )

    return {
        "summary": {
            "family": "gpcr",
            "prototype_mode": "shadow_only",
            "prototype_status": "shadow_runtime_ready",
            "prototype_variant": variant,
            "source_failure_slice": "gpcr_core_full_100k",
            "source_failure_artifact": "runs/gpcr_100k_failure_analysis_current.md",
            "source_validity_artifact": "runs/ligand_scaleup_100k_test_audit_current.md",
            "next_required_step": next_step,
        },
        "prototype": {
            "family": "gpcr",
            "domain_token": "gpcr",
            "apply_stage": "stage5_ranking",
            "training_focus": {
                "positive_anchor_count": 6,
                "false_positive_focus_topk": 20,
                "failure_rank_shift_target": "reduce last positive rank shift from +122 toward baseline-like top-k retention",
            },
            "constraints": constraints,
            "interactions": interactions,
            "tuning": tuning,
            "feature_rows": feature_rows,
            "evidence_files": [
                "runs/gpcr_100k_failure_analysis_current.md",
                "runs/global_residual_correction_target_list_current.md",
                "runs/ligand_scaleup_100k_test_audit_current.md",
                "runs/ligand_cascade_speedup_envelope_current.md",
                "runs/gpcr_residual_apply_decision_current.md",
            ],
        },
        "feature_rows": feature_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    proto = payload["prototype"]
    tuning = proto.get("tuning", {}) if isinstance(proto.get("tuning", {}), dict) else {}
    lines = [
        "# GPCR Residual Prototype Spec",
        "",
        f"- family: `{summary['family']}`",
        f"- prototype_mode: `{summary['prototype_mode']}`",
        f"- prototype_status: `{summary['prototype_status']}`",
        f"- prototype_variant: `{summary.get('prototype_variant', 'current')}`",
        f"- source_failure_slice: `{summary['source_failure_slice']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Constraints",
        "",
        f"- max_abs_delta_score: `{proto['constraints']['max_abs_delta_score']}`",
        f"- yellow_band_abs_delta_score: `{proto['constraints']['yellow_band_abs_delta_score']}`",
        f"- preserve_top2_binders: `{proto['constraints']['preserve_top2_binders']}`",
        f"- require_energy_contact_support_for_positive_delta: `{proto['constraints']['require_energy_contact_support_for_positive_delta']}`",
        f"- reference_scaling_mode: `{proto['constraints']['reference_scaling_mode']}`",
        "",
        "## Tuning",
        "",
        f"- variant: `{tuning.get('variant', 'current')}`",
        f"- min_prior_pressure_for_delta: `{tuning.get('min_prior_pressure_for_delta', 0.0)}`",
        f"- min_structural_weakness_for_delta: `{tuning.get('min_structural_weakness_for_delta', 0.0)}`",
        f"- max_structural_support_for_delta: `{tuning.get('max_structural_support_for_delta', 'unbounded')}`",
        f"- require_distance_above_z: `{tuning.get('require_distance_above_z', 'off')}`",
        f"- require_contact_below_z: `{tuning.get('require_contact_below_z', 'off')}`",
        "",
        "## Feature Targets",
        "",
        "| feature_name | role | direction | rationale |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["feature_rows"]:
        lines.append(
            f"| {row['feature_name']} | {row['role']} | {row['direction']} | {row['rationale']} |"
        )
    lines.extend(["", "## Interaction Terms", ""])
    for item in proto["interactions"]:
        lines.append(f"- `{item}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the current GPCR residual prototype spec from the measured 100k failure slice.")
    parser.add_argument("--variant", choices=["current", "narrow_v2", "chembl50_v3", "chembl50_v4"], default="current")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(variant=str(args.variant))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["feature_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
