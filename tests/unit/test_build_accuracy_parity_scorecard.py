from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_accuracy_parity_scorecard as mod

ROOT = Path(__file__).resolve().parents[2]


def test_default_pose_gap_uses_latest_v16_adaptive_packet() -> None:
    assert (
        mod.DEFAULT_GPCR_POSE_GAP_JSON
        == "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
    )
    assert mod.DEFAULT_OPENMM_EXTERNAL_JSON == "runs/openmm_2bead_strict_multitarget_current_accuracy_external.json"
    assert mod.DEFAULT_OPENMM_STABILITY_JSON == "runs/openmm_2bead_strict_multitarget_current_long_stability_validation.json"
    assert mod.DEFAULT_GPCR_RANKING_JSON == "runs/gpcr_rank_rescue_crossfit_repeat_r1_evidence_packet_current.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_scorecard_blocks_broad_claims_with_current_gap_shapes(tmp_path: Path) -> None:
    local_accuracy = tmp_path / "local_accuracy.json"
    openmm_external = tmp_path / "openmm_external.json"
    openmm_stability = tmp_path / "openmm_stability.json"
    gpcr_ranking = tmp_path / "gpcr_ranking.json"
    gpcr_core = tmp_path / "gpcr_core.json"
    drd2_repair = tmp_path / "drd2_repair.json"
    drd2_support = tmp_path / "drd2_support.json"
    full_forcefield_readiness = tmp_path / "full_forcefield_readiness.json"
    parameterization_probe = tmp_path / "parameterization_probe.json"
    protein_repair = tmp_path / "protein_repair.json"
    pose_gap = tmp_path / "pose_gap.json"
    structure_scorecard = tmp_path / "missing_structure_scorecard.json"
    wetlab = tmp_path / "wetlab.json"
    wetlab_allatom = tmp_path / "wetlab_allatom.json"
    readiness = tmp_path / "readiness.json"

    _write_json(
        local_accuracy,
        {
            "summary": {"pass": True, "targets": 11},
            "parity_summary": {"avg_neighbor_jaccard": 1.0, "avg_force_rmse_raw": 0.18},
        },
    )
    _write_json(
        openmm_external,
        {"summary": {"targets": 1, "avg_rmsd": 0.059, "avg_rmsd_vs_native": 0.036}},
    )
    _write_json(
        openmm_stability,
        {"summary": {"targets": 1, "passed_targets": 1, "avg_energy_drift_ratio_mean": 0.00028}},
    )
    _write_json(
        gpcr_ranking,
        {
            "summary": {
                "claim_promotion_allowed": False,
                "blockers": ["ci_low_below_threshold"],
                "ranking_pr_auc": 0.5187,
                "ranking_pr_auc_ci_low": 0.1486,
                "ranking_topk_hit_rate": 0.25,
                "positive_count": 9,
                "worst_positive_global_rank": 18923,
                "worst_positive_within_target_rank": 5315,
            }
        },
    )
    _write_json(
        gpcr_core,
        {"summary": {"claim_safe": False, "primary_blocker_task": "gpcr_core_full"}},
    )
    _write_json(
        drd2_repair,
        {
            "summary": {
                "claim_promotion_allowed": False,
                "positive_global_rank": 18923,
                "positive_within_target_rank": 5315,
                "decoys_above_positive_count": 5314,
                "positive_backmapping_atom_coverage_ratio": 0.142857,
                "blockers": ["drd2_positive_tail_rank", "pose_preservation_rmsd_missing"],
            }
        },
    )
    _write_json(
        drd2_support,
        {
            "summary": {
                "positive_backmapping_atom_coverage_ratio": 0.142857,
                "positive_full_atom_typed_backmapping_ready": False,
                "positive_pose_preservation_rmsd_A_p90": 0.27,
                "positive_local_minimization_survival_fraction": None,
                "positive_blockers": [
                    "backmapping_atom_coverage_below_min",
                    "full_atom_typed_backmapping_missing",
                    "local_minimization_survival_missing",
                ],
            }
        },
    )
    _write_json(
        full_forcefield_readiness,
        {
            "summary": {
                "status": "blocked",
                "full_forcefield_minimization_ready": False,
                "protein_parameterization_available": False,
                "ligand_parameterization_available": False,
                "missing_dependencies": ["openff.toolkit", "openmmforcefields"],
                "missing_assets": ["chimerax_tleap"],
            }
        },
    )
    _write_json(
        parameterization_probe,
        {
            "summary": {
                "claim_grade_parameterization_ready": False,
                "local_probe_partial": True,
                "ligand_template_parameterization_available": True,
            }
        },
    )
    _write_json(
        protein_repair,
        {
            "summary": {
                "missing_heavy_atom_residue_count": 70,
                "incomplete_histidine_count": 2,
                "claim_grade_repair_allowed": False,
            }
        },
    )
    _write_json(
        pose_gap,
        {
            "summary": {
                "blocked_positive_count": 3,
                "top20_positive_count": 1,
                "blocker_counts": {"positive_anchor_support_missing": 2},
            }
        },
    )
    _write_json(
        wetlab,
        {
            "summary": {
                "translation_quality_ready": False,
                "translation_gate_focus_status": "borderline",
                "translation_gate_focus_score": 68.1,
                "commercial_hard_gate_pass": True,
                "claim_promotion_allowed": False,
                "primary_blocker": "binding_energy_proxy_too_weak_for_translation",
                "failed_quality_axes": ["binding_energy_proxy"],
                "missing_quality_axes": ["pose_preservation_rmsd", "replicate_pass_fraction"],
                "best_mean_min_distance_A": 2.12,
                "best_binding_energy_proxy": -0.146,
            }
        },
    )
    _write_json(
        wetlab_allatom,
        {
            "summary": {
                "translation_gate_focus_status": "fail",
                "translation_gate_focus_source_status": "borderline",
                "translation_gate_focus_hard_status": "fail",
                "translation_gate_focus_score": 68.1,
                "commercial_hard_gate_pass_v2": False,
                "commercial_overall_score_v2": 54.7,
                "commercial_decision_class_v2": "commercial_review_only",
                "commercial_risk_bucket_v2": "high",
                "commercial_primary_upgrade_actions_v2": ["clear_translation_hard_gate"],
                "commercial_hard_gate_failed_metrics_v2": [
                    "translation_gate_focus_status",
                    "focus_shortlist_tier",
                    "recommended_next_expensive_lane",
                ],
                "next_required_step": "Review manually only; do not treat as wetlab-ready.",
            }
        },
    )
    _write_json(
        readiness,
        {
            "summary": {
                "core_commercial_lane_score": 82.5,
                "all_category_expansion_score": 68.9,
                "ligand_scaleup_commercialization_ready_suite_count": 0,
                "ligand_scaleup_suite_count": 3,
            }
        },
    )

    payload = mod.build_scorecard(
        local_accuracy_json=local_accuracy,
        openmm_external_json=openmm_external,
        openmm_stability_json=openmm_stability,
        gpcr_ranking_json=gpcr_ranking,
        gpcr_core_diagnostics_json=gpcr_core,
        gpcr_drd2_repair_json=drd2_repair,
        gpcr_drd2_backmapping_support_json=drd2_support,
        gpcr_drd2_full_forcefield_readiness_json=full_forcefield_readiness,
        gpcr_drd2_parameterization_probe_json=parameterization_probe,
        gpcr_drd2_protein_repair_json=protein_repair,
        gpcr_pose_gap_json=pose_gap,
        structure_scorecard_json=structure_scorecard,
        wetlab_translation_json=wetlab,
        wetlab_allatom_review_json=wetlab_allatom,
        commercial_readiness_json=readiness,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    rows = {row["axis"]: row for row in payload["rows"]}
    assert summary["status"] == "blocked_accuracy_parity"
    assert summary["overall_commercial_tool_accuracy_parity_allowed"] is False
    assert summary["pass_row_count"] == 0
    assert summary["restricted_pass_row_count"] == 1
    assert summary["blocked_row_count"] == 3
    assert summary["missing_row_count"] == 1
    assert rows["physics_dynamics"]["status"] == "restricted_pass"
    assert "openmm_reference_target_count_too_small" in rows["physics_dynamics"]["blockers"]
    assert rows["ligand_ranking"]["status"] == "blocked"
    assert "ranking_pr_auc_ci_low_below_threshold" in rows["ligand_ranking"]["blockers"]
    assert rows["pose_geometry"]["status"] == "blocked"
    assert "positive_backmapping_atom_coverage_below_threshold" in rows["pose_geometry"]["blockers"]
    assert "full_forcefield_minimization_not_ready" in rows["pose_geometry"]["blockers"]
    assert "ligand_parameterization_ligand_only_not_full_complex" in rows["pose_geometry"]["blockers"]
    assert "protein_missing_heavy_atom_residues_present" in rows["pose_geometry"]["blockers"]
    assert rows["pose_geometry"]["metrics"]["drd2_full_forcefield_minimization_ready"] is False
    assert rows["pose_geometry"]["metrics"]["drd2_protein_missing_heavy_atom_residue_count"] == 70
    assert rows["pose_geometry"]["metrics"]["drd2_incomplete_histidine_count"] == 2
    assert rows["pose_geometry"]["metrics"]["drd2_ligand_template_parameterization_available"] is True
    assert rows["pose_geometry"]["metrics"]["drd2_local_parameterization_probe_partial"] is True
    assert rows["pose_geometry"]["metrics"]["drd2_missing_forcefield_assets"] == ["chimerax_tleap"]
    assert rows["structure_refinement"]["status"] == "missing"
    assert rows["wetlab_translation"]["status"] == "blocked"
    assert rows["wetlab_translation"]["metrics"]["translation_gate_focus_status"] == "fail"
    assert rows["wetlab_translation"]["metrics"]["commercial_hard_gate_pass"] is False
    assert rows["wetlab_translation"]["metrics"]["commercial_overall_score_v2"] == 54.7
    assert "commercial_hard_gate_blocked" in rows["wetlab_translation"]["blockers"]
    assert "translation_gate_focus_status" in rows["wetlab_translation"]["blockers"]
    assert payload["claim_boundary"]["api_productization_out_of_scope"] is True


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    good = tmp_path / "good.json"
    missing_structure = tmp_path / "structure_missing.json"
    out_json = tmp_path / "scorecard.json"
    out_md = tmp_path / "scorecard.md"
    _write_json(
        good,
        {
            "summary": {
                "pass": True,
                "targets": 1,
                "ranking_pr_auc": 0.1,
                "ranking_pr_auc_ci_low": 0.01,
                "ranking_topk_hit_rate": 0.0,
                "claim_promotion_allowed": False,
                "translation_quality_ready": False,
            },
            "parity_summary": {},
        },
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_accuracy_parity_scorecard.py"),
            "--local-accuracy-json",
            str(good),
            "--openmm-external-json",
            str(good),
            "--openmm-stability-json",
            str(good),
            "--gpcr-ranking-json",
            str(good),
            "--gpcr-core-diagnostics-json",
            str(good),
            "--gpcr-drd2-repair-json",
            str(good),
            "--gpcr-drd2-backmapping-support-json",
            str(good),
            "--gpcr-drd2-full-forcefield-readiness-json",
            str(good),
            "--gpcr-drd2-parameterization-probe-json",
            str(good),
            "--gpcr-drd2-protein-repair-json",
            str(good),
            "--gpcr-pose-gap-json",
            str(good),
            "--structure-scorecard-json",
            str(missing_structure),
            "--wetlab-translation-json",
            str(good),
            "--wetlab-allatom-review-json",
            str(good),
            "--commercial-readiness-json",
            str(good),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "accuracy_parity_scorecard"
    assert "Accuracy Parity Scorecard" in out_md.read_text(encoding="utf-8")


def test_ligand_ranking_reads_stage5_metric_shape(tmp_path: Path) -> None:
    ranking = tmp_path / "stage5_ranking.json"
    core = tmp_path / "core.json"
    _write_json(
        ranking,
        {
            "metrics": {
                "pr_auc": 0.879215438805593,
                "positive_count": 13,
                "probability_score_col_used": "binding_score_composite_v7_residual_active",
            },
            "metrics_ci_unique": {"pr_auc": {"low": 0.6758817928374873}},
            "topk_unique": [{"k": 20, "hit_rate": 0.6}],
        },
    )
    _write_json(core, {"summary": {"claim_safe": False, "primary_blocker_task": "gpcr_core_full"}})

    row = mod._ligand_ranking_row(gpcr_ranking_json=ranking, gpcr_core_diagnostics_json=core)

    assert row["status"] == "restricted_pass"
    assert row["metrics"]["ranking_pr_auc"] == 0.879215
    assert row["metrics"]["ranking_pr_auc_ci_low"] == 0.675882
    assert row["metrics"]["ranking_topk_hit_rate"] == 0.6
    assert row["metrics"]["positive_count"] == 13
    assert row["metrics"]["ranking_score_col_used"] == "binding_score_composite_v7_residual_active"
    assert "claim_promotion_not_allowed" in row["blockers"]
    assert "ranking_pr_auc_ci_low_below_threshold" not in row["blockers"]
    assert "independent repeat" in row["next_required_step"]


def test_ligand_ranking_uses_rank_rescue_evidence_without_broad_claim(tmp_path: Path) -> None:
    ranking = tmp_path / "rank_rescue_evidence.json"
    core = tmp_path / "core.json"
    child_ranking = "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json"
    _write_json(
        ranking,
        {
            "summary": {
                "status": "metric_pass_claim_ready",
                "claim_promotion_allowed": True,
                "validation_claim_promotion_allowed": True,
                "broad_gpcr_claim_allowed": False,
                "router_claim_allowed": False,
                "platform_claim_allowed": False,
                "independent_repeat_completed": True,
                "crossfit_validation_ready": True,
                "label_derived_weight_selection": False,
                "ranking_pr_auc": 0.8718530390764964,
                "ranking_pr_auc_ci_low": 0.7611678630724843,
                "ranking_topk_hit_rate": 1.0,
                "positive_count": 34,
                "ranking_score_col_used": "binding_score_composite_v7_coverage_v2_crossfit_rank_rescue_shadow",
                "blockers": [],
            },
            "source_artifacts": [child_ranking],
        },
    )
    _write_json(core, {"summary": {"claim_safe": False, "primary_blocker_task": "gpcr_core_full"}})

    row = mod._ligand_ranking_row(gpcr_ranking_json=ranking, gpcr_core_diagnostics_json=core)

    assert row["status"] == "restricted_pass"
    assert row["commercial_parity_claim_allowed"] is False
    assert row["metrics"]["ranking_pr_auc"] == 0.871853
    assert row["metrics"]["ranking_pr_auc_ci_low"] == 0.761168
    assert row["metrics"]["ranking_topk_hit_rate"] == 1.0
    assert row["metrics"]["positive_count"] == 34
    assert row["metrics"]["broad_gpcr_claim_allowed"] is False
    assert row["metrics"]["validation_claim_promotion_allowed"] is True
    assert row["metrics"]["independent_repeat_completed"] is True
    assert "broad_gpcr_claim_not_allowed" in row["blockers"]
    assert "ranking_pr_auc_below_threshold" not in row["blockers"]
    assert child_ranking in row["source_artifacts"]
    assert "OPRM1" in row["next_required_step"]


def test_structure_row_exposes_internal_true_metric_backend(tmp_path: Path) -> None:
    scorecard = tmp_path / "structure_scorecard.json"
    _write_json(
        scorecard,
        {
            "summary": {
                "claim_promotion_allowed": True,
                "target_count": 3,
                "rmsd_pass": True,
                "tm_score_pass": True,
                "gdt_pass": True,
                "lddt_pass": True,
                "dockq_pass": True,
                "metric_backend": "internal_deterministic_ca_true_metrics",
                "chain_aware_canonical_ca_matching": True,
                "tm_score_true_metric_available_count": 3,
                "gdt_ts_true_metric_available_count": 3,
                "lddt_ca_true_metric_available_count": 3,
                "best_tm_score": 0.91,
                "best_gdt_ts": 0.82,
                "best_lddt_ca": 0.76,
                "molprobity_full_atom_quality_caveat": True,
                "blockers": [],
            }
        },
    )

    row = mod._structure_row(structure_scorecard_json=scorecard)

    assert row["status"] == "pass"
    assert row["metrics"]["metric_backend"] == "internal_deterministic_ca_true_metrics"
    assert row["metrics"]["chain_aware_canonical_ca_matching"] is True
    assert row["metrics"]["tm_score_true_metric_available_count"] == 3
    assert row["metrics"]["gdt_ts_true_metric_available_count"] == 3
    assert row["metrics"]["lddt_ca_true_metric_available_count"] == 3
    assert row["metrics"]["best_tm_score"] == 0.91
    assert row["metrics"]["molprobity_full_atom_quality_caveat"] is True
