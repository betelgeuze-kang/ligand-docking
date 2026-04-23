#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/idp_kalman_feature_state_smoothing_plan_current.json"
DEFAULT_OUT_MD = "runs/idp_kalman_feature_state_smoothing_plan_current.md"
DEFAULT_DOC_MD = "docs/idp_kalman_feature_state_smoothing_plan.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def build_payload() -> dict[str, Any]:
    return {
        "summary": {
            "status": "literature_anchor_default_mask_ready",
            "scope": "feature_state_smoothing_only",
            "coordinate_correction": False,
            "ranking_override": False,
            "gate_override": False,
            "default_feature_mask": "rg_sasa_only",
            "next_required_step": "Adopt rg_sasa_only as the default literature-anchor shadow mask, keep broader full-IDP corrected-path promotion blocked, and use future broader reruns only after provisional-anchor and corrected-path risks are reduced.",
        },
        "feature_groups": [
            {
                "group": "contact_derived",
                "features": ["on_contact_persistence", "anchor_contact_persistence", "contact_summary_features"],
            },
            {
                "group": "distance_compactness_derived",
                "features": ["mean_min_distance", "compactness_score", "condensation_score"],
            },
            {
                "group": "state_branch_posteriors",
                "features": ["branch_probabilities", "state_probabilities", "condition_group_posteriors"],
            },
            {
                "group": "ensemble_summary",
                "features": ["on_rg_mean", "on_sasa_proxy_mean", "on_ensemble_diversity", "on_transient_helicity"],
            },
        ],
        "promotion_checkpoints": [
            {
                "checkpoint": "tau_k18_baseline_replay_ensemble_only",
                "status": "pass",
                "gate_change_count": 0,
                "state_change_count": 0,
            },
            {
                "checkpoint": "tau_k18_baseline_replay_rg_sasa_only",
                "status": "pass",
                "gate_change_count": 0,
                "state_change_count": 0,
                "recommended_default": True,
            },
            {
                "checkpoint": "literature_anchor_subset_rg_sasa_only",
                "status": "pass",
                "gate_change_count": 0,
                "state_change_count": 0,
                "corrected_pass_folds": 7,
                "fold_count": 7,
                "recommended_default": True,
            },
        ],
        "insertion_points": [
            {
                "file": "tools/run_idp_3bead_evaluator.py",
                "purpose": "Emit feature_state_v1 shadow telemetry after raw feature assembly without touching coordinates.",
            },
            {
                "file": "tools/run_idp_3bead_holdout_pipeline.py",
                "purpose": "Pass through feature_state_v1 shadow args into evaluator runs.",
            },
            {
                "file": "runs/cross_family_residual_shadow_layer_current.md",
                "purpose": "Report IDP as feature_state_smoothing_only in the global shell.",
            },
        ],
        "telemetry": [
            "kf_applied",
            "kf_feature_count",
            "kf_mean_abs_delta",
            "kf_max_abs_delta",
            "kf_obs_noise_scale",
            "kf_process_noise_scale",
            "kf_shadow_status",
            "would_have_changed_state",
            "would_have_changed_gate",
        ],
        "guardrails": [
            "no_coordinate_correction",
            "no_raw_column_overwrite",
            "no_ranking_override",
            "no_gate_override",
            "kf_prefix_only_for_smoothed_columns",
            "delta_caps_and_disagreement_escalation",
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Kalman Feature/State Smoothing Plan",
        "",
        f"- status: `{summary['status']}`",
        f"- scope: `{summary['scope']}`",
        f"- coordinate_correction: `{summary['coordinate_correction']}`",
        f"- ranking_override: `{summary['ranking_override']}`",
        f"- gate_override: `{summary['gate_override']}`",
        f"- default_feature_mask: `{summary['default_feature_mask']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Feature Groups",
        "",
        "| group | features |",
        "| --- | --- |",
    ]
    for row in payload["feature_groups"]:
        lines.append(f"| {row['group']} | {', '.join(row['features'])} |")
    lines.extend(
        [
            "",
            "## Promotion Checkpoints",
            "",
            "| checkpoint | status | state_changes | gate_changes | recommended_default | coverage |",
            "| --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for row in payload["promotion_checkpoints"]:
        coverage = ""
        if row.get("fold_count"):
            coverage = f"{row.get('corrected_pass_folds', '')}/{row.get('fold_count', '')}"
        lines.append(
            f"| `{row['checkpoint']}` | `{row['status']}` | {row['state_change_count']} | {row['gate_change_count']} | `{row.get('recommended_default', False)}` | {coverage} |"
        )
    lines.extend(
        [
            "",
            "## Insertion Points",
            "",
            "| file | purpose |",
            "| --- | --- |",
        ]
    )
    for row in payload["insertion_points"]:
        lines.append(f"| `{row['file']}` | {row['purpose']} |")
    lines.extend(
        [
            "",
            "## Telemetry",
            "",
        ]
    )
    for item in payload["telemetry"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
        ]
    )
    for item in payload["guardrails"]:
        lines.append(f"- `{item}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the current IDP Kalman feature/state smoothing plan artifact.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--doc-md", default=DEFAULT_DOC_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    _write_json(_resolve(args.out_json), payload)
    _write_markdown(_resolve(args.out_md), payload)
    _write_markdown(_resolve(args.doc_md), payload)


if __name__ == "__main__":
    main()
