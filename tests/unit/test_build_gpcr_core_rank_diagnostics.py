from __future__ import annotations

import csv
import json
from argparse import Namespace
from pathlib import Path

from tools.gpcr_replay import build_gpcr_core_rank_diagnostics as mod


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_builds_positive_ranks_and_preserves_claim_safe_false(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    _write_json(
        runs / "ligand_scaleup_benchmark_summary_current.json",
        {
            "claim_safe": False,
            "claim_safe_status": "regression_guardrail_failed",
            "regression_diagnostics": {"primary_regression_task_id": "gpcr_core_full"},
        },
    )
    _write_json(
        runs / "gpcr_scaleup_regression_triage_current.json",
        {
            "summary": {
                "claim_safe": False,
                "primary_blocker_task": "gpcr_core_full",
            },
            "candidates": [
                {
                    "candidate_id": "gpcr_core_candidate_v1",
                    "pass": False,
                    "claim_allowed": False,
                    "comparison_only": True,
                    "reject_evidence": True,
                }
            ],
        },
    )
    prefix = "external_validation_2026-05-02_candidate_v1_set1_core_blind_gpcr_core_full_p0_n100000_r1"
    _write_json(
        runs / f"{prefix}_stage5_ranking_summary.json",
        {
            "pass": True,
            "score_col": "binding_score_composite_v7_residual_active",
            "metrics": {"pr_auc": 0.42},
        },
    )
    _write_csv(
        runs / f"{prefix}_stage5_ranking_topk.csv",
        [
            {"k": "10", "hit_rate": "0.1", "enrichment_factor": "50", "hits": "1"},
            {"k": "20", "hit_rate": "0.1", "enrichment_factor": "50", "hits": "2"},
        ],
    )
    _write_csv(
        runs / f"{prefix}_stage5_ranking_rows.csv",
        [
            {
                "target": "ADRB2",
                "ligand_id": "binder_a",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-10.0",
                "role": "far_ood_eval",
            },
            {
                "target": "ADRB2",
                "ligand_id": "decoy_a",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-9.0",
                "role": "far_ood_eval",
            },
            {
                "target": "ADRB2",
                "ligand_id": "binder_b",
                "is_binder": "true",
                "binding_score_composite_v7_residual_active": "-8.0",
                "role": "far_ood_eval",
            },
        ],
    )

    payload = mod.build_payload(
        Namespace(
            benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
            triage_json="runs/gpcr_scaleup_regression_triage_current.json",
            artifact_glob="runs/external_validation_*gpcr_core_full*stage5_ranking_summary.json",
            out_json="runs/gpcr_core_rank_diagnostics_current.json",
            out_md="runs/gpcr_core_rank_diagnostics_current.md",
        )
    )

    assert payload["summary"]["claim_safe"] is False
    assert payload["summary"]["candidate_count"] == 1
    candidate = payload["candidates"][0]
    assert candidate["candidate_id"] == "gpcr_core_candidate_v1"
    assert candidate["score_column"] == "binding_score_composite_v7_residual_active"
    assert candidate["pass"] is False
    assert candidate["source_artifacts"]["ranking_rows_csv"].endswith("_stage5_ranking_rows.csv")
    assert candidate["metrics"]["pr_auc"] == 0.42
    assert candidate["metrics"]["top20_hit_rate"] == 0.1
    assert candidate["positive_count"] == 2
    assert candidate["positive_ligand_ranks"] == [
        {"rank": 1, "ligand_id": "binder_a"},
        {"rank": 3, "ligand_id": "binder_b"},
    ]
    assert candidate["top20_positive_hits"] == [
        {"rank": 1, "ligand_id": "binder_a"},
        {"rank": 3, "ligand_id": "binder_b"},
    ]
    assert candidate["claim_allowed"] is False
    assert candidate["comparison_only"] is True
    assert candidate["reject_evidence"] is True


def test_missing_true_inputs_do_not_make_claim_safe_true(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    _write_json(runs / "ligand_scaleup_benchmark_summary_current.json", {"claim_safe": True})
    _write_json(runs / "gpcr_scaleup_regression_triage_current.json", {"summary": {"claim_safe": True}})

    payload = mod.build_payload(
        Namespace(
            benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
            triage_json="runs/gpcr_scaleup_regression_triage_current.json",
            artifact_glob="runs/external_validation_*gpcr_core_full*stage5_ranking_summary.json",
            out_json="runs/gpcr_core_rank_diagnostics_current.json",
            out_md="runs/gpcr_core_rank_diagnostics_current.md",
        )
    )

    assert payload["summary"]["claim_safe"] is False
    assert payload["summary"]["claim_safe_status"] == "diagnostic_only_not_claim_safe"
    assert payload["summary"]["candidate_count"] == 0


def test_fixed_reference_decoy_intrusion_diagnostics_include_stage3_and_top20_composition(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    _write_json(runs / "ligand_scaleup_benchmark_summary_current.json", {"claim_safe": False})
    _write_json(runs / "gpcr_scaleup_regression_triage_current.json", {"summary": {"claim_safe": False}})

    prefix = "external_validation_2026-05-02_fixed_reference_decoy_intrusion_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1"
    _write_json(
        runs / f"{prefix}_stage5_ranking_summary.json",
        {
            "pass": False,
            "score_col": "binding_score_composite_v7_residual_active",
            "metrics": {"pr_auc": 0.03277392108447956},
        },
    )
    _write_csv(
        runs / f"{prefix}_stage5_ranking_topk.csv",
        [
            {"k": "10", "hit_rate": "0.0", "enrichment_factor": "0.0", "hits": "0"},
            {"k": "20", "hit_rate": "0.05", "enrichment_factor": "83.3", "hits": "1"},
        ],
    )
    ranking_rows = []
    for rank in range(1, 21):
        is_binder = rank == 11
        ranking_rows.append(
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "carvedilol" if is_binder else f"decoy_ADRB2_GPCR_BLIND_{rank:05d}",
                "is_binder": "1" if is_binder else "0",
                "binding_score_composite_v7_residual_active": str(-1.0 + rank / 100.0),
                "mean_min_distance_A": str(4.0 + rank / 10.0),
                "role": "far_ood_eval",
            }
        )
    _write_csv(runs / f"{prefix}_stage5_ranking_rows.csv", ranking_rows)
    _write_json(
        runs / f"{prefix}_stage3_summary.json",
        {
            "active_score_col": "binding_score_composite_v7_residual_active",
            "ranking_score_col_used": "binding_score_composite_v7_residual_active",
            "score_reference_scaling": {
                "mode": "fixed_family_reference",
                "status": "loaded",
                "stats_hash": "57707bcda155f609045ad63049c81c9457a36f8f1c8144e50846ce0f45a3a034",
                "applied_columns": [
                    "binding_energy_mmpbsa_kcal_mol_proxy",
                    "mean_min_distance_A",
                ],
                "missing_columns": [],
                "fallback_columns": [],
                "invalid_columns": [],
            },
        },
    )
    _write_csv(
        runs / f"{prefix}_stage3_scores.csv",
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "decoy_ADRB2_GPCR_BLIND_00001",
                "score_scaling_mode": "fixed_family_reference",
                "score_reference_stats_hash": "57707bcda155f609045ad63049c81c9457a36f8f1c8144e50846ce0f45a3a034",
            }
        ],
    )
    _write_json(
        runs / f"{prefix}_summary.json",
        {
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "stages": {
                "stage6_operational_gate": {
                    "failed_metrics": [
                        {"metric": "ranking_pr_auc", "observed": 0.03277392108447956, "threshold": 0.5},
                        {"metric": "topk_hit_rate@20", "observed": 0.05, "threshold": 0.1},
                    ]
                }
            },
        },
    )
    _write_json(
        runs / "external_validation_2026-05-02_fixed_reference_decoy_intrusion_r1_set1_core_blind_gpcr_core_full_summary.json",
        {
            "pass": False,
            "planned_runs": 1,
            "completed_runs": 1,
            "runs": [
                {
                    "ranking_pr_auc": 0.03277392108447956,
                    "topk_hit_rate": 0.05,
                    "ranking_positive_count": 6.0,
                    "failed_stage": "stage6_operational_gate",
                }
            ],
        },
    )

    payload = mod.build_payload(
        Namespace(
            benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
            triage_json="runs/gpcr_scaleup_regression_triage_current.json",
            artifact_glob="runs/external_validation_*fixed_reference_decoy_intrusion*stage5_ranking_summary.json",
            out_json="runs/gpcr_core_rank_diagnostics_current.json",
            out_md="runs/gpcr_core_rank_diagnostics_current.md",
        )
    )

    candidate = payload["candidates"][0]
    assert candidate["candidate_id"] == "gpcr_core_fixed_reference_decoy_intrusion_v1"
    assert candidate["mode"] == "fixed_reference_apply"
    assert candidate["pass"] is False
    assert candidate["reject_evidence"] is True
    assert candidate["metrics"]["pr_auc"] == 0.03277392108447956
    assert candidate["metrics"]["top20_hit_rate"] == 0.05
    assert candidate["top20_composition"]["binder_count"] == 1
    assert candidate["top20_composition"]["decoy_count"] == 19
    assert candidate["top20_composition"]["rows"][0]["ligand_id"] == "decoy_ADRB2_GPCR_BLIND_00001"
    assert candidate["top20_positive_hits"] == [{"rank": 11, "ligand_id": "carvedilol"}]
    assert candidate["positive_ligand_ranks"] == [{"rank": 11, "ligand_id": "carvedilol"}]
    assert candidate["stage3"]["score_rows"] == 1
    assert candidate["stage3"]["fixed_scaling"]["mode"] == "fixed_family_reference"
    assert candidate["stage3"]["fixed_scaling"]["applied_columns"] == [
        "binding_energy_mmpbsa_kcal_mol_proxy",
        "mean_min_distance_A",
    ]
    assert candidate["stage3"]["fixed_scaling"]["stats_hash"] == (
        "57707bcda155f609045ad63049c81c9457a36f8f1c8144e50846ce0f45a3a034"
    )


def test_structure_support_candidate_matches_triage_by_top_level_profile_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    _write_json(runs / "ligand_scaleup_benchmark_summary_current.json", {"claim_safe": False})
    _write_json(
        runs / "gpcr_scaleup_regression_triage_current.json",
        {
            "summary": {"claim_safe": False},
            "candidates": [
                {
                    "candidate_id": "gpcr_core_structure_support_rescore_v1",
                    "tag": "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_structure-support-rescore-rollout-r1",
                    "mode": "guarded_apply",
                    "pass": False,
                    "claim_allowed": False,
                    "comparison_only": True,
                    "reject_evidence": True,
                }
            ],
        },
    )
    prefix = "external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full_p0_n100000_r1"
    top_level = "external_validation_2026-05-03_r1_set1_core_blind_gpcr_core_full"
    _write_json(
        runs / f"{prefix}_stage5_ranking_summary.json",
        {
            "metrics": {"pr_auc": 0.592849548112706},
            "score_col": "binding_score_composite_v7_residual_active",
        },
    )
    _write_csv(
        runs / f"{prefix}_stage5_ranking_topk.csv",
        [{"k": "20", "hit_rate": "0.25", "enrichment_factor": "416.6", "hits": "5"}],
    )
    _write_csv(
        runs / f"{prefix}_stage5_ranking_rows.csv",
        [
            {
                "target": "ADRB2",
                "ligand_id": "carvedilol",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-21.6",
                "mean_min_distance_A": "4.31",
                "role": "far_ood_eval",
            }
        ],
    )
    _write_json(
        runs / f"{top_level}_summary.json",
        {
            "profile_json": str(
                runs
                / "profiles"
                / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k_structure-support-rescore-rollout-r1.json"
            ),
            "runs": [
                {
                    "summary_json": str(runs / f"{prefix}_summary.json"),
                    "ranking_pr_auc": 0.592849548112706,
                    "topk_hit_rate": 0.25,
                    "ranking_positive_count": 6,
                    "failed_stage": "stage6_operational_gate",
                }
            ],
        },
    )
    _write_json(
        runs / f"{prefix}_summary.json",
        {
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "stages": {
                "stage6_operational_gate": {
                    "failed_metrics": [
                        {"metric": "ranking_pr_auc_ci_low", "value": 0.12868359671529103, "threshold": 0.45}
                    ]
                }
            },
        },
    )

    payload = mod.build_payload(
        Namespace(
            benchmark_summary_json="runs/ligand_scaleup_benchmark_summary_current.json",
            triage_json="runs/gpcr_scaleup_regression_triage_current.json",
            artifact_glob="runs/external_validation_2026-05-03*r1_stage5_ranking_summary.json",
            out_json="runs/gpcr_core_rank_diagnostics_current.json",
            out_md="runs/gpcr_core_rank_diagnostics_current.md",
        )
    )

    candidate = payload["candidates"][0]
    assert candidate["candidate_id"] == "gpcr_core_structure_support_rescore_v1"
    assert candidate["mode"] == "guarded_apply"
    assert candidate["reject_evidence"] is True
    assert candidate["reject_reason"]["reason"] == "operational_gate_failed"
    assert candidate["reject_reason"]["failed_stage"] == "stage6_operational_gate"
    assert [row["metric"] for row in candidate["reject_reason"]["failed_metrics"]] == [
        "ranking_pr_auc_ci_low",
    ]
    assert candidate["source_artifacts"]["top_level_summary_json"].endswith("_summary.json")
