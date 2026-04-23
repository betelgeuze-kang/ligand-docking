from __future__ import annotations

from tools import build_wetlab_tcruzi_pde_promoted_top4_review_packet as mod


def test_build_wetlab_tcruzi_pde_promoted_top4_review_packet_promotes_four_candidates() -> None:
    review_surface_payload = {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "strict_threshold_A": 2.5,
            "near_threshold_A": 3.0,
        },
        "rows": [
            {
                "ligand_id": "ligand_strict",
                "compound_name": "Strict Lead",
                "compound_name_human_readable": "Strict Lead",
                "compound_name_resolution": "human_readable",
                "smiles": "CCO",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 0.6724,
                "binding_energy_proxy": -9.1,
                "stability_score": 0.88,
                "contact_fraction": 0.81,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q1",
            },
            {
                "ligand_id": "ligand_near_1",
                "compound_name": "chembl_cache_fake123",
                "compound_name_human_readable": "",
                "compound_name_resolution": "cache_placeholder",
                "smiles": "CCC",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7565,
                "binding_energy_proxy": -8.4,
                "stability_score": 0.74,
                "contact_fraction": 0.67,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q2",
            },
            {
                "ligand_id": "ligand_near_2",
                "compound_name": "",
                "compound_name_human_readable": "",
                "compound_name_resolution": "unresolved",
                "smiles": "",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.7927,
                "binding_energy_proxy": -8.0,
                "stability_score": 0.72,
                "contact_fraction": 0.62,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q3",
            },
            {
                "ligand_id": "ligand_near_3",
                "compound_name": "",
                "compound_name_human_readable": "",
                "compound_name_resolution": "unresolved",
                "smiles": "",
                "rescue_review_band": "near_under_3p0A",
                "mean_min_distance_A": 2.9151,
                "binding_energy_proxy": -7.6,
                "stability_score": 0.68,
                "contact_fraction": 0.58,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q4",
            },
            {
                "ligand_id": "ligand_outside",
                "compound_name": "",
                "compound_name_human_readable": "",
                "compound_name_resolution": "unresolved",
                "smiles": "",
                "rescue_review_band": "outside_over_3p0A",
                "mean_min_distance_A": 3.3751,
                "binding_energy_proxy": -7.0,
                "stability_score": 0.50,
                "contact_fraction": 0.41,
                "trajectory_frames": 144,
                "ligand_model": "three_bead_implicit_hbond",
                "queue_id": "q5",
            },
        ],
    }
    three_bead_slice_payload = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
            "slice_candidate_count": 8,
            "three_bead_scores_csv": "/tmp/three_bead_slice_scores.csv",
        }
    }

    payload = mod.build_payload(review_surface_payload, three_bead_slice_payload)

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
    assert summary["target_id"] == "T. cruzi PDE"
    assert summary["shard_id"] == "20_of_20"
    assert summary["packet_scope"] == "promoted_top4_three_bead_rescue_review"
    assert summary["packet_ready"] is True
    assert summary["rescue_only_branch"] is True
    assert summary["default_lane_reopen_allowed"] is False
    assert summary["branch_to_rescue_only"] is True
    assert summary["selected_command_kind"] == "three_bead_rescue_local_refine"
    assert summary["strict_threshold_A"] == 2.5
    assert summary["near_threshold_A"] == 3.0
    assert summary["source_slice_candidate_count"] == 8
    assert summary["promoted_candidate_count"] == 4
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["near_candidate_count"] == 3
    assert summary["best_ligand_id"] == "ligand_strict"
    assert summary["best_compound_name"] == "Strict Lead"
    assert summary["best_compound_name_human_readable"] == "Strict Lead"
    assert summary["best_compound_name_resolution"] == "human_readable"
    assert summary["best_smiles"] == "CCO"
    assert summary["best_mean_min_distance_A"] == 0.672
    assert summary["best_binding_energy_proxy"] == -9.1
    assert summary["best_stability_score"] == 0.88
    assert summary["next_required_step"].startswith(
        "Use this promoted top-4 packet as the PDE rescue-only review unit"
    )

    assert [row["ligand_id"] for row in rows] == [
        "ligand_strict",
        "ligand_near_1",
        "ligand_near_2",
        "ligand_near_3",
    ]
    assert rows[0]["review_action"] == "strict_promote_rescue_only_branch"
    assert rows[0]["compound_name"] == "Strict Lead"
    assert rows[0]["compound_name_resolution"] == "human_readable"
    assert rows[1]["compound_name"] == "chembl_cache_fake123"
    assert rows[1]["compound_name_resolution"] == "cache_placeholder"
    assert rows[1]["review_action"] == "near_band_manual_review_rescue_only_branch"
    assert rows[3]["review_action"] == "near_band_manual_review_rescue_only_branch"
    assert rows[0]["promotion_band"] == "strict_under_2p5A"
    assert rows[1]["promotion_band"] == "near_under_3p0A"
