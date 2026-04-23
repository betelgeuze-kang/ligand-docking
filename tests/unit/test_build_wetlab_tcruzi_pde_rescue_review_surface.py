from __future__ import annotations

import csv
from pathlib import Path

from tools import build_wetlab_tcruzi_pde_rescue_review_surface as mod


def test_build_wetlab_tcruzi_pde_rescue_review_surface_promotes_rescue_only_branch(tmp_path: Path) -> None:
    run_dir = tmp_path / "t_cruzi_pde" / "20_of_20"
    traj_dir = run_dir / "throughput_run_gate51_stage2_traj_frames" / "shard_00000"
    traj_dir.mkdir(parents=True)
    ligand_manifest = run_dir / "ligand_manifest.csv"
    with ligand_manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ligand_id",
                "smiles",
                "compound_name",
                "source_dataset",
                "source_anchor",
                "source_url",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ligand_id": "ligand_strict",
                "smiles": "CCO",
                "compound_name": "Strict Lead",
                "source_dataset": "manifest.csv",
                "source_anchor": "anchor.csv",
                "source_url": "https://example.test/strict",
            }
        )
        writer.writerow(
            {
                "ligand_id": "ligand_near_1",
                "smiles": "CCC",
                "compound_name": "chembl_cache_fake123",
                "source_dataset": "manifest.csv",
                "source_anchor": "anchor.csv",
                "source_url": "",
            }
        )

    score_csv = tmp_path / "three_bead_slice_scores.csv"
    with score_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ligand_id",
                "binding_energy_proxy",
                "stability_score",
                "mean_min_distance_A",
                "contact_fraction",
                "trajectory_frames",
                "ligand_model",
                "queue_id",
                "trajectory_npz",
                "score_json",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ligand_id": "ligand_strict",
                "binding_energy_proxy": -9.1,
                "stability_score": 0.88,
                "mean_min_distance_A": 0.6724,
                "contact_fraction": 0.81,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q1",
                "trajectory_npz": str(traj_dir / "ligand_strict.npz"),
                "score_json": "score1.json",
            }
        )
        writer.writerow(
            {
                "ligand_id": "ligand_near_1",
                "binding_energy_proxy": -8.4,
                "stability_score": 0.74,
                "mean_min_distance_A": 2.7565,
                "contact_fraction": 0.67,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q2",
                "trajectory_npz": str(traj_dir / "ligand_near_1.npz"),
                "score_json": "score2.json",
            }
        )
        writer.writerow(
            {
                "ligand_id": "ligand_near_2",
                "binding_energy_proxy": -8.0,
                "stability_score": 0.72,
                "mean_min_distance_A": 2.9151,
                "contact_fraction": 0.62,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q3",
                "trajectory_npz": str(traj_dir / "ligand_near_2.npz"),
                "score_json": "score3.json",
            }
        )
        writer.writerow(
            {
                "ligand_id": "ligand_outside",
                "binding_energy_proxy": -7.0,
                "stability_score": 0.50,
                "mean_min_distance_A": 3.3751,
                "contact_fraction": 0.41,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q4",
                "trajectory_npz": str(traj_dir / "ligand_outside.npz"),
                "score_json": "score4.json",
            }
        )

    payload = mod.build_payload(
        hard_target_rescue_lane_payload={
            "summary": {
                "status": "wetlab_hard_target_rescue_lane_ready",
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
            }
        },
        rescue_anchor_artifacts_payload={
            "summary": {
                "status": "wetlab_rescue_anchor_artifacts_ready",
                "anchor_artifact_count": 3,
                "rescue_only": True,
            }
        },
        rescue_three_bead_candidates_payload={
            "summary": {
                "status": "wetlab_rescue_three_bead_candidates_ready",
                "candidate_count": 32,
                "selected_command_kind": "three_bead_rescue_local_refine",
            }
        },
        rescue_three_bead_slice_payload={
            "summary": {
                "status": "wetlab_rescue_three_bead_slice_ready",
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "selected_command_kind": "three_bead_rescue_local_refine",
                "selected_threshold_A": 2.5,
                "slice_candidate_count": 8,
                "three_bead_scores_csv": str(score_csv),
            }
        },
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_pde_rescue_review_surface_ready"
    assert summary["decision"] == "promote_rescue_only_branch_keep_default_closed"
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_rescue_only"] is True
    assert summary["promoted_candidate_count"] == 3
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["near_candidate_count"] == 2
    assert summary["best_ligand_id"] == "ligand_strict"
    assert summary["best_compound_name"] == "Strict Lead"
    assert summary["best_compound_name_human_readable"] == "Strict Lead"
    assert summary["best_compound_name_resolution"] == "human_readable"
    assert summary["best_smiles"] == "CCO"
    assert summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert summary["next_required_step"].startswith("Operate T. cruzi PDE as a rescue-only branch")

    assert [row["ligand_id"] for row in rows] == [
        "ligand_strict",
        "ligand_near_1",
        "ligand_near_2",
    ]
    assert rows[0]["compound_name"] == "Strict Lead"
    assert rows[0]["compound_name_human_readable"] == "Strict Lead"
    assert rows[0]["compound_name_resolution"] == "human_readable"
    assert rows[1]["compound_name"] == "chembl_cache_fake123"
    assert rows[1]["compound_name_human_readable"] == ""
    assert rows[1]["compound_name_resolution"] == "cache_placeholder"
    assert rows[0]["rescue_review_band"] == "strict_under_2p5A"
    assert rows[1]["rescue_review_band"] == "near_under_3p0A"
