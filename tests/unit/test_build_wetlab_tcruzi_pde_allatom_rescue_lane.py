from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_allatom_rescue_lane import build_payload


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_wetlab_tcruzi_pde_allatom_rescue_lane(tmp_path: Path) -> None:
    stage2_manifest = tmp_path / "throughput_run_gate51_stage2_traj_manifest.csv"
    score_csv = tmp_path / "three_bead_slice_scores.csv"
    _write_csv(stage2_manifest, [{"ligand_id": "lig_a", "trajectory_npz": "traj_a.npz"}])
    _write_csv(
        score_csv,
        [
            {
                "ligand_id": "lig_a",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.35,
                "mean_min_distance_A": 2.3,
                "contact_fraction": "",
                "trajectory_frames": "",
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_a",
                "trajectory_npz": "traj_a.npz",
                "score_json": "",
            }
        ],
    )
    branch_summary_payload = {"summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "branch_label": "tcruzi_pde_rescue_only_branch", "branch_state": "promoted_top4_packet_ready_default_lane_closed"}}
    review_packet_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "best_ligand_id": "lig_a",
            "best_mean_min_distance_A": 0.672,
            "under_2p5_candidate_count": 1,
            "near_candidate_count": 3,
            "packet_ready": True,
            "packet_ready_for_operator_review": True,
            "wetlab_final_gate_pass": True,
            "claim_gate_available": True,
            "claim_ready_for_allatom": True,
        }
    }
    rescue_review_surface_payload = {
        "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"},
        "structured": {
            "ligand_manifest_csv": str(tmp_path / "ligand_manifest.csv"),
            "three_bead_scores_csv": str(score_csv),
        },
        "rows": [
            {
                "ligand_id": "lig_a",
                "compound_name": "cmpd-a",
                "compound_name_resolution": "human_readable",
                "rescue_review_band": "strict_pass",
                "mean_min_distance_A": 2.3,
                "pose_preservation_rmsd_A": 1.6,
                "backmapping_consistency_score": 0.81,
                "local_minimization_survival_fraction": 0.83,
                "replicate_pass_fraction": 0.77,
                "smiles": "CC",
            }
        ],
    }
    _write_csv(tmp_path / "ligand_manifest.csv", [{"ligand_id": "lig_a", "compound_name": "cmpd-a", "smiles": "CC"}])
    rescue_three_bead_candidates_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "candidate_count": 1,
            "selected_command_kind": "three_bead_rescue_local_refine",
            "selected_threshold_A": 2.5,
        },
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "priority_rank": 1,
                "ligand_id": "lig_a",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.35,
                "mean_min_distance_A": 2.3,
                "pose_preservation_rmsd_A": 1.6,
                "backmapping_consistency_score": 0.81,
                "local_minimization_survival_fraction": 0.83,
                "replicate_pass_fraction": 0.77,
            }
        ],
    }
    rescue_three_bead_slice_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "stage2_manifest_csv": str(stage2_manifest),
            "trajectory_root": str(tmp_path / "traj"),
            "three_bead_scores_csv": str(score_csv),
        }
    }
    (tmp_path / "traj").mkdir()
    rescue_anchor_artifacts_payload = {"summary": {"rescue_target_native_csv": "native.csv", "rescue_target_pocket_csv": "pocket.csv", "rescue_target_ligand_csv": "lig.csv"}}

    payload = build_payload(
        branch_summary_payload,
        review_packet_payload,
        rescue_review_surface_payload,
        rescue_three_bead_candidates_payload,
        rescue_three_bead_slice_payload,
        rescue_anchor_artifacts_payload,
        top_n=1,
        default_top_k=1,
    )
    summary = payload["summary"]
    assert summary["target_id"] == "T. cruzi PDE"
    assert summary["lane_candidate_count"] == 1
    assert summary["review_packet_ready"] is True
    assert summary["review_packet_ready_for_operator_review"] is True
    assert summary["review_packet_wetlab_final_gate_pass"] is True
    assert summary["review_packet_claim_gate_available"] is True
    assert summary["review_packet_claim_ready_for_allatom"] is True
    assert summary["translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert summary["translation_gate_focus_status"] == "pass"
    assert summary["translation_gate_focus_hard_status"] == "pass"
    assert summary["translation_gate_focus_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert summary["translation_gate_focus_warning_checks"] == [
        "contact_fraction_not_observed",
        "trajectory_frames_not_observed",
    ]
    assert summary["focus_shortlist_tier"] == "tier1_gold"
    assert summary["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["recommended_next_expensive_lane_reason"] == (
        "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
    )
    assert summary["selected_command_kind"] == "pseudo_allatom_backmapping_rescore"
    assert summary["allatom_ligand_model"] == "3bead_implicit_hbond"
    assert summary["source_three_bead_metric_origin_counts"] == {"three_bead_score_csv": 1}
    assert "Focus lane `ensemble_explicit_water_mmgbsa` opens under `strict_high_confidence_translation_v2`" in summary["next_required_step"]
    assert payload["rows"][0]["compound_name"] == "cmpd-a"
    assert payload["rows"][0]["selected_command_kind"] == "pseudo_allatom_backmapping_rescore"
    assert payload["rows"][0]["selected_threshold_A"] == 2.5
    assert payload["rows"][0]["allatom_ligand_model"] == "3bead_implicit_hbond"
    assert payload["rows"][0]["resolved_rescue_review_band"] == "strict_pass"
    assert payload["rows"][0]["resolved_rescue_review_band_source"] == "source_rescue_review_band"
    assert payload["rows"][0]["translation_gate_status"] == "pass"
    assert payload["rows"][0]["translation_gate_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert payload["rows"][0]["recommended_next_expensive_lane_entry_status"] == "open"
    assert payload["rows"][0]["translation_gate_warning_checks"] == [
        "contact_fraction_not_observed",
        "trajectory_frames_not_observed",
    ]
    assert payload["rows"][0]["shortlist_tier"] == "tier1_gold"
    assert payload["rows"][0]["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert summary["translation_gate_focus_hard_status"] == "pass"
    assert summary["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["recommended_next_expensive_lane_entry_status"] == "open"
    assert summary["recommended_next_expensive_lane_gate"] == "strict_high_confidence_translation_v2"
    assert "run_ensemble_explicit_water_mmgbsa" == summary["recommended_next_expensive_lane_action"]
    assert payload["rows"][0]["translation_gate_action_codes"]


def test_build_wetlab_tcruzi_pde_allatom_rescue_lane_reports_band_metadata_drift(
    tmp_path: Path,
) -> None:
    stage2_manifest = tmp_path / "throughput_run_gate51_stage2_traj_manifest.csv"
    score_csv = tmp_path / "three_bead_slice_scores.csv"
    _write_csv(stage2_manifest, [{"ligand_id": "lig_mismatch", "trajectory_npz": "traj_mismatch.npz"}])
    _write_csv(
        score_csv,
        [
            {
                "ligand_id": "lig_mismatch",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.8,
                "mean_min_distance_A": 3.4,
                "contact_fraction": 0.6,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_mismatch",
                "trajectory_npz": "traj_mismatch.npz",
                "score_json": "",
            }
        ],
    )
    branch_summary_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "branch_label": "tcruzi_pde_rescue_only_branch",
        }
    }
    rescue_review_surface_payload = {
        "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"},
        "rows": [
            {
                "ligand_id": "lig_mismatch",
                "compound_name": "drifted candidate",
                "compound_name_resolution": "human_readable",
                "rescue_review_band": "strict_under_2p5A",
                "smiles": "CC",
            }
        ],
    }
    rescue_three_bead_candidates_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "candidate_count": 1,
        },
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "priority_rank": 1,
                "ligand_id": "lig_mismatch",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.8,
                "mean_min_distance_A": 3.4,
                "pose_preservation_rmsd_A": 1.6,
                "backmapping_consistency_score": 0.81,
                "local_minimization_survival_fraction": 0.83,
                "replicate_pass_fraction": 0.77,
            }
        ],
    }
    rescue_three_bead_slice_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "stage2_manifest_csv": str(stage2_manifest),
            "trajectory_root": str(tmp_path / "traj"),
            "three_bead_scores_csv": str(score_csv),
        }
    }

    payload = build_payload(
        branch_summary_payload,
        {},
        rescue_review_surface_payload,
        rescue_three_bead_candidates_payload,
        rescue_three_bead_slice_payload,
        {},
        top_n=1,
        default_top_k=1,
    )

    summary = payload["summary"]
    assert summary["rescue_review_band_consistency_counts"] == {"mismatch_fail_closed": 1}
    assert summary["source_rescue_review_band_mismatch_count"] == 1
    assert summary["rescue_review_band_consistency_action_codes"] == [
        "rebuild_rescue_review_band_metadata_from_numeric_distance"
    ]
    assert summary["rescue_review_band_mismatch_rows_preview"] == [
        {
            "lane_rank": 1,
            "ligand_id": "lig_mismatch",
            "source_three_bead_mean_min_distance_A": 3.4,
            "metadata_rescue_review_bucket": "strict",
            "numeric_rescue_review_bucket": "other",
            "source_rescue_review_band": "strict_under_2p5A",
            "numeric_rescue_review_band": "candidate_top32",
            "action_code": "rebuild_rescue_review_band_metadata_from_numeric_distance",
        }
    ]
    row = payload["rows"][0]
    assert row["metadata_rescue_review_bucket"] == "strict"
    assert row["source_three_bead_metric_origin"] == "three_bead_score_csv"
    assert row["numeric_rescue_review_band"] == "candidate_top32"
    assert row["numeric_rescue_review_bucket"] == "other"
    assert row["rescue_review_band_consistency_status"] == "mismatch_fail_closed"
    assert row["rescue_review_band_consistency_action_codes"] == [
        "rebuild_rescue_review_band_metadata_from_numeric_distance"
    ]


def test_build_wetlab_tcruzi_pde_allatom_rescue_lane_uses_score_csv_metric_as_canonical(
    tmp_path: Path,
) -> None:
    stage2_manifest = tmp_path / "throughput_run_gate51_stage2_traj_manifest.csv"
    score_csv = tmp_path / "three_bead_slice_scores.csv"
    _write_csv(stage2_manifest, [{"ligand_id": "lig_reconciled", "trajectory_npz": "traj_reconciled.npz"}])
    _write_csv(
        score_csv,
        [
            {
                "ligand_id": "lig_reconciled",
                "binding_energy_proxy": -2.0,
                "stability_score": 0.9,
                "mean_min_distance_A": 2.3,
                "contact_fraction": 0.6,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_reconciled",
                "trajectory_npz": "traj_reconciled.npz",
                "score_json": "",
            }
        ],
    )
    branch_summary_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "branch_label": "tcruzi_pde_rescue_only_branch",
        }
    }
    rescue_review_surface_payload = {
        "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"},
        "rows": [
            {
                "ligand_id": "lig_reconciled",
                "compound_name": "review-sourced candidate",
                "compound_name_resolution": "human_readable",
                "rescue_review_band": "strict_under_2p5A",
                "mean_min_distance_A": 2.3,
                "binding_energy_proxy": -2.0,
                "stability_score": 0.9,
                "pose_preservation_rmsd_A": 1.5,
                "backmapping_consistency_score": 0.82,
                "local_minimization_survival_fraction": 0.84,
                "replicate_pass_fraction": 0.78,
                "smiles": "CC",
            }
        ],
    }
    rescue_three_bead_candidates_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "candidate_count": 1,
        },
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "priority_rank": 1,
                "ligand_id": "lig_reconciled",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.8,
                "mean_min_distance_A": 3.4,
                "pose_preservation_rmsd_A": 1.6,
                "backmapping_consistency_score": 0.81,
                "local_minimization_survival_fraction": 0.83,
                "replicate_pass_fraction": 0.77,
            }
        ],
    }
    rescue_three_bead_slice_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "stage2_manifest_csv": str(stage2_manifest),
            "trajectory_root": str(tmp_path / "traj"),
            "three_bead_scores_csv": str(score_csv),
        }
    }

    payload = build_payload(
        branch_summary_payload,
        {},
        rescue_review_surface_payload,
        rescue_three_bead_candidates_payload,
        rescue_three_bead_slice_payload,
        {},
        top_n=1,
        default_top_k=1,
    )

    summary = payload["summary"]
    assert summary["rescue_review_band_consistency_counts"] == {"match": 1}
    assert summary["source_rescue_review_band_mismatch_count"] == 0
    assert summary["source_three_bead_metric_origin_counts"] == {"three_bead_score_csv": 1}
    assert summary["source_three_bead_metric_reconciled_count"] == 1
    row = payload["rows"][0]
    assert row["source_three_bead_metric_origin"] == "three_bead_score_csv"
    assert row["source_three_bead_metric_origin_artifact"] == str(score_csv)
    assert row["candidate_seed_mean_min_distance_A"] == 3.4
    assert row["review_surface_mean_min_distance_A"] == 2.3
    assert row["score_csv_mean_min_distance_A"] == 2.3
    assert row["source_three_bead_mean_min_distance_A"] == 2.3
    assert row["source_three_bead_binding_energy_proxy"] == -2.0
    assert row["numeric_rescue_review_band"] == "strict_under_2p5A"
    assert row["rescue_review_band_consistency_status"] == "match"
    assert row["metric_reconciled"] is True


def test_build_wetlab_tcruzi_pde_allatom_rescue_lane_keeps_score_csv_other_out_of_near_band(
    tmp_path: Path,
) -> None:
    stage2_manifest = tmp_path / "throughput_run_gate51_stage2_traj_manifest.csv"
    score_csv = tmp_path / "three_bead_slice_scores.csv"
    _write_csv(stage2_manifest, [{"ligand_id": "lig_095456", "trajectory_npz": "traj_095456.npz"}])
    _write_csv(
        score_csv,
        [
            {
                "ligand_id": "lig_095609",
                "binding_energy_proxy": 0.1134,
                "stability_score": 0.4936,
                "mean_min_distance_A": 0.672,
                "contact_fraction": 0.5289,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_095609",
                "trajectory_npz": "traj_095609.npz",
                "score_json": "",
            },
            {
                "ligand_id": "lig_095204",
                "binding_energy_proxy": -0.0869,
                "stability_score": 0.3187,
                "mean_min_distance_A": 2.756,
                "contact_fraction": 0.51,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_095204",
                "trajectory_npz": "traj_095204.npz",
                "score_json": "",
            },
            {
                "ligand_id": "lig_095202",
                "binding_energy_proxy": -0.1364,
                "stability_score": 0.3225,
                "mean_min_distance_A": 2.793,
                "contact_fraction": 0.52,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_095202",
                "trajectory_npz": "traj_095202.npz",
                "score_json": "",
            },
            {
                "ligand_id": "lig_095028",
                "binding_energy_proxy": -0.1451,
                "stability_score": 0.3195,
                "mean_min_distance_A": 2.915,
                "contact_fraction": 0.53,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_095028",
                "trajectory_npz": "traj_095028.npz",
                "score_json": "",
            },
            {
                "ligand_id": "lig_095456",
                "binding_energy_proxy": -0.1523,
                "stability_score": 0.3921,
                "mean_min_distance_A": 3.375,
                "contact_fraction": 0.54,
                "trajectory_frames": 300,
                "ligand_model": "3bead_implicit_hbond",
                "queue_id": "queue_095456",
                "trajectory_npz": "traj_095456.npz",
                "score_json": "",
            },
        ],
    )
    rescue_review_surface_payload = {
        "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"},
        "structured": {"three_bead_scores_csv": str(score_csv)},
        "rows": [
            {"ligand_id": "lig_095609", "rescue_review_band": "strict_under_2p5A", "mean_min_distance_A": 0.672},
            {"ligand_id": "lig_095204", "rescue_review_band": "near_under_3p0A", "mean_min_distance_A": 2.756},
            {"ligand_id": "lig_095202", "rescue_review_band": "near_under_3p0A", "mean_min_distance_A": 2.793},
            {"ligand_id": "lig_095028", "rescue_review_band": "near_under_3p0A", "mean_min_distance_A": 2.915},
        ],
    }
    rescue_three_bead_candidates_payload = {
        "summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "candidate_count": 5},
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "priority_rank": 1,
                "ligand_id": "lig_095456",
                "binding_energy_proxy": -1.0,
                "stability_score": 0.8,
                "mean_min_distance_A": 2.638,
            }
        ],
    }
    rescue_three_bead_slice_payload = {
        "summary": {
            "target_id": "T. cruzi PDE",
            "shard_id": "20_of_20",
            "stage2_manifest_csv": str(stage2_manifest),
            "trajectory_root": str(tmp_path / "traj"),
            "three_bead_scores_csv": str(score_csv),
        }
    }

    payload = build_payload(
        {"summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"}},
        {},
        rescue_review_surface_payload,
        rescue_three_bead_candidates_payload,
        rescue_three_bead_slice_payload,
        {},
        top_n=5,
        default_top_k=8,
        default_filter_mode="strict_then_near_fill",
    )

    summary = payload["summary"]
    assert summary["lane_candidate_count"] == 5
    assert summary["strict_band_candidate_count"] == 1
    assert summary["near_band_candidate_count"] == 3
    assert summary["other_band_candidate_count"] == 1
    assert summary["source_rescue_review_band_mismatch_count"] == 0
    assert summary["rescue_review_band_consistency_counts"] == {"match": 5}
    assert summary["source_three_bead_metric_origin_counts"] == {"three_bead_score_csv": 5}

    row_095456 = next(row for row in payload["rows"] if row["ligand_id"] == "lig_095456")
    assert row_095456["source_three_bead_mean_min_distance_A"] == 3.375
    assert row_095456["candidate_seed_mean_min_distance_A"] == 2.638
    assert row_095456["resolved_rescue_review_band"] == "candidate_top32"
    assert row_095456["numeric_rescue_review_band"] == "candidate_top32"
    assert row_095456["numeric_rescue_review_bucket"] == "other"
    assert row_095456["rescue_review_band_consistency_status"] == "match"
    assert row_095456["metric_reconciled"] is True
