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
    _write_csv(stage2_manifest, [{"ligand_id": "lig_a", "trajectory_npz": "traj_a.npz"}])
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
    rescue_review_surface_payload = {"summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20"}, "structured": {"ligand_manifest_csv": str(tmp_path / "ligand_manifest.csv")}, "rows": [{"ligand_id": "lig_a", "compound_name": "cmpd-a", "compound_name_resolution": "human_readable", "rescue_review_band": "strict_pass", "smiles": "CC"}]}
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
    rescue_three_bead_slice_payload = {"summary": {"target_id": "T. cruzi PDE", "shard_id": "20_of_20", "stage2_manifest_csv": str(stage2_manifest), "trajectory_root": str(tmp_path / "traj")}}
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
