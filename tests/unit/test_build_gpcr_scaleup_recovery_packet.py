from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_gpcr_scaleup_recovery_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_ranking_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["target", "ligand_id", "is_binder", "reference_binding_kcal_mol", "binding_score_composite_v7_residual_active", "mean_min_distance_A", "role"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _task_summary_payload(
    *,
    passed: bool,
    failed_stage: str | None,
    ranking_pr_auc: float,
    ranking_pr_auc_ci_low: float,
    ranking_topk_hit_rate: float,
    ranking_ef1: float,
    ranking_bedroc: float,
    ranking_unique_auc: float,
    ranking_positive_count: int,
    mean_min_distance_A: float,
    min_frames_observed: int,
    score_col: str,
) -> dict:
    return {
        "pass": passed,
        "failed_stage": failed_stage,
        "stages": {
            "stage6_operational_gate": {
                "failed_metrics": [
                    {"metric": "ranking_pr_auc", "value": ranking_pr_auc, "threshold": 0.55},
                    {"metric": "ranking_pr_auc_ci_low", "value": ranking_pr_auc_ci_low, "threshold": 0.45},
                    {"metric": "topk_hit_rate@20", "value": ranking_topk_hit_rate, "threshold": 0.2},
                ]
                if not passed
                else [],
                "mean_min_distance_A": mean_min_distance_A,
                "min_frames_observed": min_frames_observed,
                "ranking_bedroc": ranking_bedroc,
                "ranking_pr_auc": ranking_pr_auc,
                "ranking_pr_auc_ci_low": ranking_pr_auc_ci_low,
                "ranking_positive_count": ranking_positive_count,
                "ranking_score_col_used": score_col,
                "ranking_topk_hit_rate": ranking_topk_hit_rate,
                "ranking_unique_auc": ranking_unique_auc,
                "ranking_ef1": ranking_ef1,
            }
        },
        "service_result": {"failed_stage": failed_stage},
    }


def _stage3_payload(*, spec_json: str, active_score_col: str, tuning_variant: str, positive_delta_count: int) -> dict:
    return {
        "residual_prototype": {
            "family": "gpcr",
            "mode": "apply",
            "spec_json": spec_json,
            "active_score_col": active_score_col,
            "tuning_variant": tuning_variant,
            "positive_delta_count": positive_delta_count,
            "gated_positive_delta_count": positive_delta_count,
            "mean_delta": 3.5e-05,
            "max_delta": 0.35,
            "min_prior_pressure_for_delta": 0.96,
            "min_raw_delta_for_activation": 0.38,
            "min_structural_weakness_for_delta": 0.98,
            "status": "apply_ready",
            "yellow_band_count": 1,
        }
    }


def test_build_gpcr_scaleup_recovery_packet_from_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "runs/external_validation_blind_runs/external_validation_blind_runs_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1"
    core_summary_json = source_root / "set1_core_blind/files/gpcr/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json"
    chembl50_summary_json = source_root / "set2_expanded_ood/files/gpcr/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json"
    core_pipeline_summary_json = tmp_path / "runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1_summary.json"
    chembl50_pipeline_summary_json = tmp_path / "runs/external_validation_2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1_set2_expanded_ood_gpcr_chembl50_full_p0_n100000_r1_summary.json"
    core_stage3_json = core_pipeline_summary_json.with_name(
        core_pipeline_summary_json.name.replace("_summary.json", "_stage3_summary.json")
    )
    chembl50_stage3_json = chembl50_pipeline_summary_json.with_name(
        chembl50_pipeline_summary_json.name.replace("_summary.json", "_stage3_summary.json")
    )
    core_rows_csv = core_pipeline_summary_json.with_name(
        core_pipeline_summary_json.name.replace("_summary.json", "_stage5_ranking_rows.csv")
    )
    chembl50_rows_csv = chembl50_pipeline_summary_json.with_name(
        chembl50_pipeline_summary_json.name.replace("_summary.json", "_stage5_ranking_rows.csv")
    )

    _write_json(
        source_root / "summary.json",
        {
            "tag": "2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1",
            "generated_at_local": "2026-04-30T22:01:11",
            "out_root": str(source_root),
            "summary": {
                "claim_safe": False,
                "commercial_scaleup_ready": False,
                "decision": "keep_gpcr_scaleup_blocked_for_core_claims",
                "plain_language": "ChEMBL50 expanded-OOD lane passes, but gpcr_core_full still fails operational PR-AUC/top20 guardrails, so 100k/1m commercial scale-up claims must remain blocked.",
                "router_promotion_allowed": False,
                "status": "core_blocked_chembl50_passed",
            },
            "next_required_work": [
                "Do not promote chembl50_v4 residual apply as a core GPCR scale-up repair.",
                "Design a new GPCR core hard-decoy scoring/residual candidate that directly penalizes prior-structure mismatch and weak contact support among top-ranked decoys.",
                "Acceptance for the next candidate: gpcr_core_full PR-AUC >= 0.55, PR-AUC CI low >= 0.45, top20 hit rate >= 0.20, while ChEMBL50 remains operational-gate pass.",
                "Only after core and expanded-OOD both pass should the scale-up summary and commercialization queue be refreshed for 100k/1m claims.",
            ],
            "root_cause_hypothesis": {
                "evidence": ["core residual positive_delta_count=1 across 4 scored rows"],
                "primary": "Residual-v4 apply is too sparse for gpcr_core_full hard-decoy intrusion.",
            },
            "residual_effect": {
                "chembl50": {
                    "gated_positive_delta_count": 4,
                    "max_delta": 0.35,
                    "mean_delta": 3.5e-05,
                    "min_prior_pressure_for_delta": 0.96,
                    "min_raw_delta_for_activation": 0.38,
                    "min_structural_weakness_for_delta": 0.98,
                    "positive_delta_count": 4,
                    "status": "apply_ready",
                    "yellow_band_count": 1,
                },
                "core": {
                    "gated_positive_delta_count": 1,
                    "max_delta": 0.35,
                    "mean_delta": 3.5e-05,
                    "min_prior_pressure_for_delta": 0.96,
                    "min_raw_delta_for_activation": 0.38,
                    "min_structural_weakness_for_delta": 0.98,
                    "positive_delta_count": 1,
                    "status": "apply_ready",
                    "yellow_band_count": 1,
                },
            },
            "sets": [
                {
                    "set_id": "set1_core_blind",
                    "tasks": [
                        {
                            "task_id": "gpcr_core_full",
                            "summary_json": str(core_summary_json),
                            "pipeline_summary_json": str(core_pipeline_summary_json),
                        }
                    ],
                },
                {
                    "set_id": "set2_expanded_ood",
                    "tasks": [
                        {
                            "task_id": "gpcr_chembl50_full",
                            "summary_json": str(chembl50_summary_json),
                            "pipeline_summary_json": str(chembl50_pipeline_summary_json),
                        }
                    ],
                },
            ],
        },
    )

    _write_json(
        core_summary_json,
        _task_summary_payload(
            passed=False,
            failed_stage="stage6_operational_gate",
            ranking_pr_auc=0.388769891374058,
            ranking_pr_auc_ci_low=0.02178617927752618,
            ranking_topk_hit_rate=0.15,
            ranking_ef1=66.66666666666667,
            ranking_bedroc=1.0,
            ranking_unique_auc=0.9948135547995464,
            ranking_positive_count=2,
            mean_min_distance_A=4.440798493345579,
            min_frames_observed=120,
            score_col="binding_score_composite_v7_residual_active",
        ),
    )
    _write_json(
        chembl50_summary_json,
        _task_summary_payload(
            passed=True,
            failed_stage=None,
            ranking_pr_auc=0.8312014911003694,
            ranking_pr_auc_ci_low=0.7388261993626117,
            ranking_topk_hit_rate=1.0,
            ranking_ef1=83.92857142857143,
            ranking_bedroc=1.0,
            ranking_unique_auc=0.9965000430984944,
            ranking_positive_count=3,
            mean_min_distance_A=4.448934954653184,
            min_frames_observed=120,
            score_col="binding_score_composite_v7_residual_active",
        ),
    )
    _write_json(
        core_stage3_json,
        _stage3_payload(
            spec_json="runs/gpcr_residual_prototype_spec_chembl50_v4_current.json",
            active_score_col="binding_score_composite_v7_residual_active",
            tuning_variant="chembl50_v4",
            positive_delta_count=4,
        ),
    )
    _write_json(
        chembl50_stage3_json,
        _stage3_payload(
            spec_json="runs/gpcr_residual_prototype_spec_chembl50_v4_current.json",
            active_score_col="binding_score_composite_v7_residual_active",
            tuning_variant="chembl50_v4",
            positive_delta_count=1,
        ),
    )

    _write_ranking_rows(
        core_rows_csv,
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-1", "is_binder": 1, "reference_binding_kcal_mol": -9.1, "binding_score_composite_v7_residual_active": -14.1, "mean_min_distance_A": 4.1, "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-2", "is_binder": 1, "reference_binding_kcal_mol": -8.5, "binding_score_composite_v7_residual_active": -13.9, "mean_min_distance_A": 4.0, "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "decoy-1", "is_binder": 0, "reference_binding_kcal_mol": -2.95, "binding_score_composite_v7_residual_active": -13.2, "mean_min_distance_A": 4.2, "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-3", "is_binder": 1, "reference_binding_kcal_mol": -10.2, "binding_score_composite_v7_residual_active": -12.4, "mean_min_distance_A": 4.3, "role": "far_ood_eval"},
        ],
    )
    _write_ranking_rows(
        chembl50_rows_csv,
        [
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-a", "is_binder": 1, "reference_binding_kcal_mol": -12.7, "binding_score_composite_v7_residual_active": -21.0, "mean_min_distance_A": 4.6, "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-b", "is_binder": 1, "reference_binding_kcal_mol": -12.0, "binding_score_composite_v7_residual_active": -20.3, "mean_min_distance_A": 4.5, "role": "far_ood_eval"},
            {"target": "ADRB2_GPCR_BLIND", "ligand_id": "binder-c", "is_binder": 1, "reference_binding_kcal_mol": -11.9, "binding_score_composite_v7_residual_active": -19.5, "mean_min_distance_A": 4.4, "role": "far_ood_eval"},
        ],
    )

    payload = mod.build_payload(
        source_run_root=str(source_root),
        generated_at_local="2026-04-30T22:31:23",
    )

    assert payload["artifact_type"] == "gpcr_scaleup_100k_residualv4_apply_recovery_packet"
    assert payload["candidate"]["tag"] == "2026-04-30_gpcr_scaleup_100k_residualv4_apply_candidate_v1"
    assert payload["candidate"]["residual_spec_json"].endswith("runs/gpcr_residual_prototype_spec_chembl50_v4_current.json")
    assert payload["lanes"]["core"]["failed_stage"] == "stage6_operational_gate"
    assert payload["lanes"]["core"]["failed_metrics"][0]["metric"] == "ranking_pr_auc"
    assert payload["lanes"]["core"]["ranking_counts"]["positive_ranks"] == [1, 2, 4]
    assert payload["lanes"]["core"]["ranking_counts"]["top20_false_positive_count"] == 1
    assert payload["lanes"]["chembl50"]["pass"] is True
    assert payload["lanes"]["chembl50"]["ranking_counts"]["positive_count"] == 3
    assert payload["residual_effect"]["core"]["status"] == "apply_ready"
    assert payload["residual_effect"]["core"]["positive_delta_count"] == 1
    assert payload["residual_effect"]["chembl50"]["positive_delta_count"] == 4
    assert "core residual positive_delta_count=1 across 4 scored rows" in payload["root_cause_hypothesis"]["evidence"]
    assert payload["summary"]["status"] == "core_blocked_chembl50_passed"
    assert payload["summary"]["claim_safe"] is False
    assert payload["next_required_work"][0].startswith("Do not promote chembl50_v4")
