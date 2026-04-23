from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_wetlab_rescue_three_bead_candidates as mod
from tools import build_wetlab_hard_target_rescue_lane as rescue_lane_mod


def test_build_wetlab_rescue_three_bead_candidates_uses_stage3_topn(tmp_path: Path) -> None:
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "ligand_id",
                "binding_score_composite_v7_residual_active",
                "binding_energy_proxy",
                "stability_score",
                "contact_fraction",
                "mean_min_distance_A",
                "trajectory_frames",
                "pose_preservation_rmsd_A",
                "backmapping_consistency_score",
                "local_minimization_survival_fraction",
                "replicate_pass_fraction",
            ],
        )
        writer.writeheader()
        writer.writerow(
                {
                    "target": "T. cruzi PDE",
                    "ligand_id": "ligA",
                    "binding_score_composite_v7_residual_active": "0.10",
                    "binding_energy_proxy": "-0.7",
                    "stability_score": "0.7",
                    "contact_fraction": "0.9",
                    "mean_min_distance_A": "2.9",
                "trajectory_frames": "200",
                "pose_preservation_rmsd_A": "2.0",
                "backmapping_consistency_score": "0.80",
                "local_minimization_survival_fraction": "0.80",
                "replicate_pass_fraction": "0.76",
            }
        )
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "ligB",
                "binding_score_composite_v7_residual_active": "0.90",
                "binding_energy_proxy": "-1.4",
                "stability_score": "0.9",
                "contact_fraction": "0.8",
                "mean_min_distance_A": "3.4",
                "trajectory_frames": "180",
                "pose_preservation_rmsd_A": "2.9",
                "backmapping_consistency_score": "0.40",
                "local_minimization_survival_fraction": "0.45",
                "replicate_pass_fraction": "0.35",
            }
        )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "summary_json": str(summary_json),
                    "top_n_three_bead_recommended": True,
                    "top_n_three_bead_count": 2,
                }
            ]
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_rescue_three_bead_candidates_ready"
    assert summary["candidate_row_count"] == 2
    assert summary["selection_score_col"] == "binding_score_composite_v7_residual_active"
    assert summary["selection_score_source"] == "auto_priority"
    assert summary["focus_selection_score_value"] == 0.1
    assert summary["selection_score_cols_used"] == ["binding_score_composite_v7_residual_active"]
    assert payload["rows"][0]["ligand_id"] == "ligA"
    assert payload["rows"][1]["ligand_id"] == "ligB"
    assert payload["rows"][0]["selection_score_col"] == "binding_score_composite_v7_residual_active"
    assert payload["rows"][0]["selection_score_source"] == "auto_priority"
    assert payload["rows"][0]["selection_score_value"] == 0.1
    assert payload["rows"][1]["selection_score_value"] == 0.9
    assert payload["rows"][0]["translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert payload["rows"][0]["recommended_next_expensive_lane"] == "seed_replicated_short_md_consensus"
    assert payload["rows"][1]["translation_gate_hard_status"] == "fail"
    assert payload["rows"][1]["recommended_next_expensive_lane"] == "defer_expensive_lane"


def test_annotate_translation_gate_row_v2_surfaces_repairable_translation_breaks() -> None:
    annotated = mod.annotate_translation_gate_row(
        {
            "mean_min_distance_A": 2.8,
            "binding_energy_proxy": -0.9,
            "stability_score": 0.72,
            "contact_fraction": 0.61,
            "trajectory_frames": 180,
            "pose_preservation_rmsd_A": 3.1,
            "backmapping_consistency_score": 0.42,
            "local_minimization_survival_fraction": 0.48,
            "replicate_pass_fraction": 0.38,
        },
        review_band="near_under_3p0A",
    )

    assert annotated["translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert annotated["translation_gate_status"] == "borderline"
    assert annotated["translation_gate_hard_status"] == "repairable_fail"
    assert annotated["recommended_next_expensive_lane"] == "pose_repair_then_explicit_water_minimization"
    assert annotated["recommended_next_expensive_lane_entry_status"] == "repair_then_reopen"
    assert "pose_preservation_breaks_translation" in annotated["translation_gate_blocker_codes"]
    assert "repair_pose_preservation_geometry" in annotated["translation_gate_action_codes"]
    assert "run_pose_repair_then_explicit_water_minimization" == annotated["recommended_next_expensive_lane_action"]


def test_rescue_three_bead_candidates_fall_back_to_stage6_and_retry_sources(tmp_path: Path, monkeypatch) -> None:
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["ligand_id", "binding_energy_proxy", "stability_score", "mean_min_distance_A"],
        )
        writer.writeheader()
        writer.writerow({"ligand_id": "lig1", "binding_energy_proxy": "-1.0", "stability_score": "0.9", "mean_min_distance_A": "5.0"})

    def fake_load_json(path: str) -> dict:
        if path == "stage6.json":
            return {"summary": {"status": "wetlab_primary_stage6_failure_surface_ready"}}
        if path == "retry.json":
            return {"summary": {"status": "wetlab_target_retry_policy_templates_ready"}}
        return {}

    monkeypatch.setattr(mod, "load_json", fake_load_json)
    monkeypatch.setattr(
        rescue_lane_mod,
        "build_payload",
        lambda stage6_payload, retry_payload: {
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "summary_json": str(summary_json),
                    "top_n_three_bead_recommended": True,
                    "top_n_three_bead_count": 1,
                }
            ]
        },
    )

    resolved = mod._resolve_rescue_lane_payload(
        {},
        rescue_lane_json="rescue.json",
        stage6_failure_surface_json="stage6.json",
        retry_policy_templates_json="retry.json",
    )
    payload = mod.build_payload(resolved, top_n=1)

    assert payload["summary"]["candidate_row_count"] == 1
    assert payload["rows"][0]["ligand_id"] == "lig1"


def test_build_wetlab_rescue_three_bead_candidates_separates_translation_gate_and_expensive_lane_choices(
    tmp_path: Path,
) -> None:
    summary_dir = tmp_path / "runs" / "wetlab_broad_screen_throughput" / "t_cruzi_pde" / "20_of_20"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_json = summary_dir / "throughput_run_summary.json"
    summary_json.write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
    with (summary_dir / "throughput_run_stage3_scores.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "target",
                "ligand_id",
                "binding_score_composite_v7_residual_active",
                "binding_energy_proxy",
                "stability_score",
                "contact_fraction",
                "mean_min_distance_A",
                "trajectory_frames",
                "pose_preservation_rmsd_A",
                "backmapping_consistency_score",
                "local_minimization_survival_fraction",
                "replicate_pass_fraction",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "lig_strong",
                "binding_score_composite_v7_residual_active": "0.10",
                "binding_energy_proxy": "-1.1",
                "stability_score": "0.85",
                "contact_fraction": "0.90",
                "mean_min_distance_A": "2.20",
                "trajectory_frames": "240",
                "pose_preservation_rmsd_A": "1.7",
                "backmapping_consistency_score": "0.82",
                "local_minimization_survival_fraction": "0.84",
                "replicate_pass_fraction": "0.76",
            }
        )
        writer.writerow(
            {
                "target": "T. cruzi PDE",
                "ligand_id": "lig_fail",
                "binding_score_composite_v7_residual_active": "0.90",
                "binding_energy_proxy": "-0.2",
                "stability_score": "0.20",
                "contact_fraction": "0.35",
                "mean_min_distance_A": "3.40",
                "trajectory_frames": "90",
                "pose_preservation_rmsd_A": "3.1",
                "backmapping_consistency_score": "0.40",
                "local_minimization_survival_fraction": "0.41",
                "replicate_pass_fraction": "0.32",
            }
        )

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "summary_json": str(summary_json),
                    "top_n_three_bead_recommended": True,
                    "top_n_three_bead_count": 2,
                }
            ]
        },
        top_n=2,
    )

    summary = payload["summary"]
    assert summary["candidate_row_count"] == 2
    assert summary["translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert summary["translation_gate_pass_count"] == 1
    assert summary["translation_gate_fail_count"] == 1
    assert summary["translation_gate_focus_status"] == "pass"
    assert summary["translation_gate_focus_hard_status"] == "pass"
    assert summary["translation_gate_focus_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert summary["translation_gate_focus_warning_checks"] == []
    assert summary["focus_shortlist_tier"] == "tier1_gold"
    assert summary["focus_recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["focus_recommended_next_expensive_lane_reason"] == (
        "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
    )
    assert summary["recommended_next_expensive_lane_counts"] == [
        {"recommended_next_expensive_lane": "defer_expensive_lane", "candidate_count": 1},
        {"recommended_next_expensive_lane": "ensemble_explicit_water_mmgbsa", "candidate_count": 1},
    ]

    strong_row = payload["rows"][0]
    fail_row = payload["rows"][1]
    assert strong_row["ligand_id"] == "lig_strong"
    assert strong_row["translation_gate_status"] == "pass"
    assert strong_row["translation_gate_hard_status"] == "pass"
    assert strong_row["translation_gate_required_pass_count"] == 3
    assert strong_row["translation_gate_optional_pass_count"] == 6
    assert strong_row["translation_gate_requires_pose_tightening"] is False
    assert strong_row["translation_gate_warning_checks"] == []
    assert strong_row["shortlist_tier"] == "tier1_gold"
    assert strong_row["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert strong_row["recommended_next_expensive_lane_reason"] == (
        "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
    )
    assert fail_row["ligand_id"] == "lig_fail"
    assert fail_row["translation_gate_status"] == "fail"
    assert fail_row["translation_gate_hard_status"] == "fail"
    assert fail_row["translation_gate_reason"] == (
        "3-bead evidence is too weak for direct all-atom translation without repair."
    )
    assert fail_row["translation_gate_failed_checks"] == [
        "backmapping_consistency_too_low",
        "binding_energy_proxy_too_weak_for_translation",
        "distance_above_translation_near_band",
        "local_minimization_survival_too_low",
        "pose_preservation_rmsd_too_high",
        "replicate_pass_fraction_too_low",
        "stability_too_low_for_translation",
    ]
    assert fail_row["translation_gate_warning_checks"] == [
        "contact_fraction_below_support_target",
        "trajectory_support_sparse",
    ]
    assert fail_row["shortlist_tier"] == "defer"
    assert fail_row["recommended_next_expensive_lane"] == "defer_expensive_lane"
    assert fail_row["recommended_next_expensive_lane_reason"] == (
        "Do not spend stronger-physics budget until the translation hard gate or survival support improves."
    )
