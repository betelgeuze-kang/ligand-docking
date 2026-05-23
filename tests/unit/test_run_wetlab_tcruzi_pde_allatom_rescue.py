from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from tools.wetlab_target_render_utils import write_artifact
from tools.run_wetlab_tcruzi_pde_allatom_rescue import main, run


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_single_ready_rescue_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    stage1_queue = tmp_path / "stage1.csv"
    stage2_manifest = tmp_path / "stage2.csv"
    traj_root = tmp_path / "traj"
    traj_root.mkdir()
    (traj_root / "strict.npz").write_bytes(b"strict trajectory")
    _write_csv(stage1_queue, [{"ligand_id": "ligand_strict", "trajectory_npz": "strict.npz"}])
    _write_csv(stage2_manifest, [{"ligand_id": "ligand_strict", "trajectory_npz": "strict.npz"}])
    lane_md = tmp_path / "lane.md"
    write_artifact(
        str(lane_md),
        "lane",
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "base_stage1_queue_csv": str(stage1_queue),
                "base_stage2_manifest_csv": str(stage2_manifest),
                "base_trajectory_root": str(traj_root),
                "rescue_target_native_csv": "native.csv",
                "rescue_target_pocket_csv": "pocket.csv",
                "rescue_target_ligand_csv": "lig.csv",
            },
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "lane_rank": 1,
                    "ligand_id": "ligand_strict",
                    "compound_name": "strict lead",
                    "compound_name_human_readable": "Strict Lead",
                    "compound_name_resolution": "human_readable",
                    "smiles": "CCO",
                    "source_three_bead_priority_rank": 1,
                    "source_three_bead_binding_energy_proxy": -9.0,
                    "source_three_bead_stability_score": 0.8,
                    "source_three_bead_mean_min_distance_A": 2.2,
                    "source_three_bead_pose_preservation_rmsd_A": 1.7,
                    "source_three_bead_backmapping_consistency_score": 0.82,
                    "source_three_bead_local_minimization_survival_fraction": 0.84,
                    "source_three_bead_replicate_pass_fraction": 0.75,
                    "source_rescue_review_band": "strict_under_2p5A",
                    "rescue_target_native_csv": "native.csv",
                    "rescue_target_pocket_csv": "pocket.csv",
                    "rescue_target_ligand_csv": "lig.csv",
                },
            ],
        },
    )
    claim_json = tmp_path / "claim_readiness.json"
    equivalence_json = tmp_path / "equivalence_gate.json"
    _write_json(
        claim_json,
        {"summary": {"policy_version": "test_policy_v1", "pass_core_gate": True, "claim_ready_for_allatom": True}},
    )
    _write_json(equivalence_json, {"summary": {"policy_version": "test_policy_v1", "claim_ready_for_allatom": True}})
    return lane_md.with_suffix(".json"), claim_json, equivalence_json


def test_run_wetlab_tcruzi_pde_allatom_rescue_execute_false(tmp_path: Path, monkeypatch) -> None:
    stage1_queue = tmp_path / "stage1.csv"
    stage2_manifest = tmp_path / "stage2.csv"
    traj_root = tmp_path / "traj"
    traj_root.mkdir()
    _write_csv(stage1_queue, [{"ligand_id": "lig_a"}])
    _write_csv(stage2_manifest, [{"ligand_id": "lig_a", "trajectory_npz": "traj_a.npz"}])
    lane_md = tmp_path / "lane.md"
    write_artifact(
        str(lane_md),
        "lane",
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "base_stage1_queue_csv": str(stage1_queue),
                "base_stage2_manifest_csv": str(stage2_manifest),
                "base_trajectory_root": str(traj_root),
                "rescue_target_native_csv": "native.csv",
                "rescue_target_pocket_csv": "pocket.csv",
                "rescue_target_ligand_csv": "lig.csv",
            },
            "rows": [
                {"target_id": "T. cruzi PDE", "target_slug": "t_cruzi_pde", "shard_id": "20_of_20", "lane_rank": 1, "ligand_id": "lig_a", "compound_name": "cmpd-a", "compound_name_resolution": "human_readable", "smiles": "CC", "source_three_bead_priority_rank": 1, "source_three_bead_binding_energy_proxy": -1.0, "source_three_bead_stability_score": 0.3, "source_three_bead_mean_min_distance_A": 2.3, "source_rescue_review_band": "strict_pass", "rescue_target_native_csv": "native.csv", "rescue_target_pocket_csv": "pocket.csv", "rescue_target_ligand_csv": "lig.csv"},
            ],
        },
    )
    out_md = tmp_path / "runner.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_wetlab_tcruzi_pde_allatom_rescue.py",
            "--lane-json",
            str(lane_md.with_suffix(".json")),
            "--top-k",
            "1",
            "--no-execute",
            "--out-md",
            str(out_md),
        ],
    )
    main()
    payload = json.loads(out_md.with_suffix(".json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["slice_candidate_count"] == 1
    assert summary["execution_mode"] == "controller_manifest_only"
    assert summary["raw_claim_requirement_mode"] == "semi_hard"
    assert summary["raw_claim_gate_status"] == "claim_required_unavailable"
    assert summary["effective_actionability_status"] == "hard_blocked"
    assert summary["effective_primary_blocking_domain"] == "translation_gate"
    assert summary["effective_blocking_order"] == ["translation_gate", "claim_equivalence_gate"]
    assert summary["action_recipe_codes"] == [
        "raise_three_bead_stability",
        "measure_pose_preservation_rmsd",
        "measure_backmapping_consistency",
        "produce_claim_equivalence_packet",
        "defer_expensive_lane",
    ]
    assert summary["action_recipe_rows"][0]["action_recipe_code"] == "raise_three_bead_stability"
    assert summary["action_recipe_rows"][1]["action_recipe_code"] == "measure_pose_preservation_rmsd"
    assert summary["action_recipe_rows"][1]["action_recipe_status"] == "advisory"
    assert summary["action_recipe_rows"][2]["action_recipe_code"] == "measure_backmapping_consistency"
    assert summary["action_recipe_rows"][2]["action_recipe_status"] == "advisory"
    assert summary["action_recipe_rows"][3]["action_recipe_code"] == "produce_claim_equivalence_packet"
    assert summary["action_recipe_rows"][4]["action_recipe_code"] == "defer_expensive_lane"
    assert summary["effective_actionability_required_calculations"] == [
        "produce_claim_equivalence_packet",
        "raise_three_bead_stability",
    ]
    assert summary["top_k_requested"] == 1
    assert summary["top_k_effective"] == 1
    assert summary["rescue_execution_plan_status"] == "blocked_deferred"
    assert summary["rescue_execution_selected_bucket_counts"] == {"strict": 1, "near": 0, "other": 0}
    assert summary["rescue_execution_status_counts"] == [
        {"rescue_execution_status": "deferred_blocked", "count": 1}
    ]
    assert summary["rescue_execution_next_required_calculations"] == [
        "produce_claim_equivalence_packet",
        "raise_three_bead_stability",
    ]
    assert summary["rescue_execution_next_action_recipe_codes"] == [
        "raise_three_bead_stability",
        "produce_claim_equivalence_packet",
    ]
    assert summary["rescue_execution_expensive_lane_status"] == "deferred"
    assert payload["rows"][0]["action_recipe_codes"] == summary["action_recipe_codes"]
    assert payload["rows"][0]["effective_blocking_order"] == summary["effective_blocking_order"]
    assert payload["rows"][0]["rescue_execution_status"] == "deferred_blocked"
    assert payload["rows"][0]["rescue_expensive_lane_status"] == "deferred"
    assert payload["rows"][0]["rescue_next_required_calculations"] == [
        "produce_claim_equivalence_packet",
        "raise_three_bead_stability",
    ]
    assert payload["rows"][0]["rescue_next_action_recipe_codes"] == [
        "raise_three_bead_stability",
        "produce_claim_equivalence_packet",
    ]
    assert payload["rows"][0]["rescue_iteration_metadata"] == {
        "selected_rank": 1,
        "top_k_requested": 1,
        "top_k_effective": 1,
        "filter_mode_requested": "all",
        "filter_mode_applied": "all",
        "review_bucket": "strict",
        "execute_requested": False,
    }


def test_run_wetlab_tcruzi_pde_allatom_rescue_respects_filter_mode_and_claim_paths(tmp_path: Path) -> None:
    stage1_queue = tmp_path / "stage1.csv"
    stage2_manifest = tmp_path / "stage2.csv"
    traj_root = tmp_path / "traj"
    traj_root.mkdir()
    _write_csv(
        stage1_queue,
        [
            {"ligand_id": "ligand_strict", "trajectory_npz": "strict.npz"},
            {"ligand_id": "ligand_near_1", "trajectory_npz": "near_1.npz"},
            {"ligand_id": "ligand_near_2", "trajectory_npz": "near_2.npz"},
            {"ligand_id": "ligand_outside", "trajectory_npz": "outside.npz"},
        ],
    )
    _write_csv(
        stage2_manifest,
        [
            {"ligand_id": "ligand_strict", "trajectory_npz": "strict.npz"},
            {"ligand_id": "ligand_near_1", "trajectory_npz": "near_1.npz"},
            {"ligand_id": "ligand_near_2", "trajectory_npz": "near_2.npz"},
            {"ligand_id": "ligand_outside", "trajectory_npz": "outside.npz"},
        ],
    )
    lane_md = tmp_path / "lane.md"
    write_artifact(
        str(lane_md),
        "lane",
        {
            "summary": {
                "target_id": "T. cruzi PDE",
                "shard_id": "20_of_20",
                "base_stage1_queue_csv": str(stage1_queue),
                "base_stage2_manifest_csv": str(stage2_manifest),
                "base_trajectory_root": str(traj_root),
                "rescue_target_native_csv": "native.csv",
                "rescue_target_pocket_csv": "pocket.csv",
                "rescue_target_ligand_csv": "lig.csv",
            },
            "rows": [
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "lane_rank": 1,
                    "ligand_id": "ligand_strict",
                    "compound_name": "strict lead",
                    "compound_name_human_readable": "Strict Lead",
                    "compound_name_resolution": "human_readable",
                    "smiles": "CCO",
                    "source_three_bead_priority_rank": 1,
                    "source_three_bead_binding_energy_proxy": -9.0,
                    "source_three_bead_stability_score": 0.8,
                    "source_three_bead_mean_min_distance_A": 2.2,
                    "source_three_bead_pose_preservation_rmsd_A": 1.7,
                    "source_three_bead_backmapping_consistency_score": 0.82,
                    "source_three_bead_local_minimization_survival_fraction": 0.84,
                    "source_three_bead_replicate_pass_fraction": 0.75,
                    "source_rescue_review_band": "strict_under_2p5A",
                    "rescue_target_native_csv": "native.csv",
                    "rescue_target_pocket_csv": "pocket.csv",
                    "rescue_target_ligand_csv": "lig.csv",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "lane_rank": 2,
                    "ligand_id": "ligand_near_1",
                    "compound_name": "near lead 1",
                    "compound_name_human_readable": "Near Lead 1",
                    "compound_name_resolution": "human_readable",
                    "smiles": "CCC",
                    "source_three_bead_priority_rank": 2,
                    "source_three_bead_binding_energy_proxy": -8.8,
                    "source_three_bead_stability_score": 0.7,
                    "source_three_bead_mean_min_distance_A": 2.7,
                    "source_three_bead_pose_preservation_rmsd_A": 2.0,
                    "source_three_bead_backmapping_consistency_score": 0.73,
                    "source_three_bead_local_minimization_survival_fraction": 0.74,
                    "source_three_bead_replicate_pass_fraction": 0.68,
                    "source_rescue_review_band": "near_under_3p0A",
                    "rescue_target_native_csv": "native.csv",
                    "rescue_target_pocket_csv": "pocket.csv",
                    "rescue_target_ligand_csv": "lig.csv",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "lane_rank": 3,
                    "ligand_id": "ligand_near_2",
                    "compound_name": "near lead 2",
                    "compound_name_human_readable": "Near Lead 2",
                    "compound_name_resolution": "human_readable",
                    "smiles": "CCCC",
                    "source_three_bead_priority_rank": 3,
                    "source_three_bead_binding_energy_proxy": -8.6,
                    "source_three_bead_stability_score": 0.6,
                    "source_three_bead_mean_min_distance_A": 2.9,
                    "source_three_bead_pose_preservation_rmsd_A": 2.8,
                    "source_three_bead_backmapping_consistency_score": 0.44,
                    "source_three_bead_local_minimization_survival_fraction": 0.49,
                    "source_three_bead_replicate_pass_fraction": 0.36,
                    "source_rescue_review_band": "near_under_3p0A",
                    "rescue_target_native_csv": "native.csv",
                    "rescue_target_pocket_csv": "pocket.csv",
                    "rescue_target_ligand_csv": "lig.csv",
                },
                {
                    "target_id": "T. cruzi PDE",
                    "target_slug": "t_cruzi_pde",
                    "shard_id": "20_of_20",
                    "lane_rank": 4,
                    "ligand_id": "ligand_outside",
                    "compound_name": "outside lead",
                    "compound_name_human_readable": "Outside Lead",
                    "compound_name_resolution": "human_readable",
                    "smiles": "CCCCC",
                    "source_three_bead_priority_rank": 4,
                    "source_three_bead_binding_energy_proxy": -8.0,
                    "source_three_bead_stability_score": 0.5,
                    "source_three_bead_mean_min_distance_A": 3.4,
                    "source_three_bead_pose_preservation_rmsd_A": 3.1,
                    "source_three_bead_backmapping_consistency_score": 0.40,
                    "source_three_bead_local_minimization_survival_fraction": 0.41,
                    "source_three_bead_replicate_pass_fraction": 0.30,
                    "source_rescue_review_band": "outside_over_3p0A",
                    "rescue_target_native_csv": "native.csv",
                    "rescue_target_pocket_csv": "pocket.csv",
                    "rescue_target_ligand_csv": "lig.csv",
                },
            ],
        },
    )
    claim_json = tmp_path / "claim_readiness.json"
    equivalence_json = tmp_path / "equivalence_gate.json"
    _write_json(
        claim_json,
        {"summary": {"policy_version": "test_policy_v1", "pass_core_gate": True, "claim_ready_for_allatom": True}},
    )
    _write_json(equivalence_json, {"summary": {"policy_version": "test_policy_v1", "claim_ready_for_allatom": True}})

    out_md = tmp_path / "runner.md"
    payload = run(
        lane_json=str(lane_md.with_suffix(".json")),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=2,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=False,
        out_md=str(out_md),
    )

    summary = payload["summary"]
    assert summary["filter_mode_requested"] == "strict_then_near_fill"
    assert summary["filter_mode_applied"] == "strict_then_near_fill"
    assert summary["strict_band_candidate_count"] == 1
    assert summary["near_band_candidate_count"] == 2
    assert summary["filtered_lane_candidate_count"] == 3
    assert summary["slice_candidate_count"] == 2
    assert summary["top_k_requested"] == 2
    assert summary["top_k_effective"] == 2
    assert summary["rescue_execution_plan_status"] == "ready_manifest_only"
    assert summary["rescue_execution_filtered_bucket_counts"] == {"strict": 1, "near": 2, "other": 0}
    assert summary["rescue_execution_selected_bucket_counts"] == {"strict": 1, "near": 1, "other": 0}
    assert summary["rescue_execution_status_counts"] == [
        {"rescue_execution_status": "ready_manifest_only", "count": 2}
    ]
    assert summary["rescue_execution_next_required_calculations"] == [
        "run_ensemble_explicit_water_mmgbsa",
        "run_seed_replicated_short_md_consensus",
    ]
    assert summary["rescue_execution_next_action_recipe_codes"] == [
        "run_ensemble_explicit_water_mmgbsa",
        "run_seed_replicated_short_md_consensus",
    ]
    assert summary["rescue_execution_expensive_lane_status"] == "open"
    assert summary["selected_command_kind"] == "pseudo_allatom_backmapping_rescore"
    assert summary["allatom_ligand_model"] == "3bead_implicit_hbond"
    assert summary["allatom_claim_readiness_json"] == str(claim_json)
    assert summary["allatom_equivalence_gate_json"] == str(equivalence_json)
    assert summary["raw_claim_requirement_mode"] == "semi_hard"
    assert summary["raw_claim_gate_status"] == "claim_ready"
    assert summary["raw_claim_gate_satisfied"] is True
    assert summary["effective_actionability_status"] == "ready_for_expensive_lane"
    assert summary["effective_blocking_order"] == []
    assert summary["action_recipe_codes"] == ["run_ensemble_explicit_water_mmgbsa"]
    assert summary["action_recipe_rows"][0]["action_recipe_code"] == "run_ensemble_explicit_water_mmgbsa"
    assert summary["selected_translation_gate_version"] == "three_bead_to_allatom_translation_v2"
    assert summary["selected_translation_gate_pass_count"] == 2
    assert summary["selected_translation_gate_borderline_count"] == 0
    assert summary["selected_translation_gate_focus_status"] == "pass"
    assert summary["selected_translation_gate_focus_hard_status"] == "pass"
    assert summary["selected_translation_gate_focus_soft_status"] == "strong"
    assert summary["selected_translation_gate_focus_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert summary["selected_translation_gate_focus_warning_checks"] == [
        "contact_fraction_not_observed",
        "trajectory_frames_not_observed",
    ]
    assert summary["focus_shortlist_tier"] == "tier1_gold"
    assert summary["selected_shortlist_tier1_gold_count"] == 1
    assert summary["selected_shortlist_tier2_silver_count"] == 1
    assert summary["selected_shortlist_promising_count"] == 2
    assert summary["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["recommended_next_expensive_lane_entry_status"] == "open"
    assert summary["recommended_next_expensive_lane_gate"] == "strict_high_confidence_translation_v2"
    assert summary["recommended_next_expensive_lane_action"] == "run_ensemble_explicit_water_mmgbsa"
    assert summary["recommended_next_expensive_lane_reason"] == (
        "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
    )
    assert [row["ligand_id"] for row in payload["rows"]] == ["ligand_strict", "ligand_near_1"]
    assert payload["rows"][0]["selected_filter_mode_requested"] == "strict_then_near_fill"
    assert payload["rows"][0]["selected_filter_mode_applied"] == "strict_then_near_fill"
    assert payload["rows"][0]["selected_command_kind"] == "pseudo_allatom_backmapping_rescore"
    assert payload["rows"][0]["allatom_ligand_model"] == "3bead_implicit_hbond"
    assert payload["rows"][0]["resolved_rescue_review_band"] == "strict_under_2p5A"
    assert payload["rows"][0]["translation_gate_status"] == "pass"
    assert payload["rows"][0]["translation_gate_hard_status"] == "pass"
    assert payload["rows"][0]["translation_gate_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert payload["rows"][0]["translation_gate_warning_checks"] == [
        "contact_fraction_not_observed",
        "trajectory_frames_not_observed",
    ]
    assert payload["rows"][0]["shortlist_tier"] == "tier1_gold"
    assert payload["rows"][0]["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert payload["rows"][0]["recommended_next_expensive_lane_entry_status"] == "open"
    assert payload["rows"][0]["action_recipe_codes"] == ["run_ensemble_explicit_water_mmgbsa"]
    assert payload["rows"][0]["effective_blocking_order"] == []
    assert payload["rows"][0]["rescue_execution_status"] == "ready_manifest_only"
    assert payload["rows"][0]["rescue_expensive_lane_status"] == "open"
    assert payload["rows"][0]["rescue_next_required_calculations"] == ["run_ensemble_explicit_water_mmgbsa"]
    assert payload["rows"][0]["rescue_next_action_recipe_codes"] == ["run_ensemble_explicit_water_mmgbsa"]
    assert payload["rows"][0]["rescue_iteration_metadata"] == {
        "selected_rank": 1,
        "top_k_requested": 2,
        "top_k_effective": 2,
        "filter_mode_requested": "strict_then_near_fill",
        "filter_mode_applied": "strict_then_near_fill",
        "review_bucket": "strict",
        "execute_requested": False,
    }
    assert payload["rows"][0]["recommended_next_expensive_lane_reason"] == (
        "Strict-band rescue already satisfies translation v2 hard checks and replicate-aware geometry support."
    )
    assert payload["rows"][1]["resolved_rescue_review_band"] == "near_under_3p0A"
    assert payload["rows"][1]["translation_gate_status"] == "pass"
    assert payload["rows"][1]["translation_gate_hard_status"] == "pass"
    assert payload["rows"][1]["translation_gate_reason"] == (
        "3-bead geometry, energy, and survival signals are coherent enough for direct all-atom translation."
    )
    assert payload["rows"][1]["translation_gate_warning_checks"] == [
        "contact_fraction_not_observed",
        "trajectory_frames_not_observed",
    ]
    assert payload["rows"][1]["shortlist_tier"] == "tier2_silver"
    assert payload["rows"][1]["recommended_next_expensive_lane"] == "seed_replicated_short_md_consensus"
    assert payload["rows"][1]["action_recipe_codes"] == ["run_seed_replicated_short_md_consensus"]
    assert payload["rows"][1]["rescue_execution_status"] == "ready_manifest_only"
    assert payload["rows"][1]["rescue_expensive_lane_status"] == "open"
    assert payload["rows"][1]["rescue_next_required_calculations"] == [
        "run_seed_replicated_short_md_consensus"
    ]
    assert payload["rows"][1]["rescue_iteration_metadata"]["selected_rank"] == 2
    assert payload["rows"][1]["rescue_iteration_metadata"]["review_bucket"] == "near"
    assert payload["rows"][1]["recommended_next_expensive_lane_reason"] == (
        "Translation passes the hard gate, but replicate-aware validation should precede explicit-water spend."
    )


def test_run_wetlab_tcruzi_pde_allatom_rescue_fails_closed_on_band_distance_mismatch(
    tmp_path: Path,
) -> None:
    lane_json, claim_json, equivalence_json = _write_single_ready_rescue_inputs(tmp_path)
    lane_payload = json.loads(lane_json.read_text(encoding="utf-8"))
    stage1_queue = Path(lane_payload["summary"]["base_stage1_queue_csv"])
    stage2_manifest = Path(lane_payload["summary"]["base_stage2_manifest_csv"])
    mismatch_row = dict(lane_payload["rows"][0])
    mismatch_row.update(
        {
            "ligand_id": "ligand_mismatch",
            "lane_rank": 1,
            "source_three_bead_mean_min_distance_A": 3.4,
            "source_rescue_review_band": "strict_under_2p5A",
        }
    )
    near_row = dict(lane_payload["rows"][0])
    near_row.update(
        {
            "ligand_id": "ligand_near",
            "lane_rank": 2,
            "source_three_bead_mean_min_distance_A": 2.7,
            "source_rescue_review_band": "near_under_3p0A",
        }
    )
    lane_payload["rows"] = [mismatch_row, near_row]
    _write_json(lane_json, lane_payload)
    _write_csv(
        stage1_queue,
        [
            {"ligand_id": "ligand_mismatch", "trajectory_npz": "mismatch.npz"},
            {"ligand_id": "ligand_near", "trajectory_npz": "near.npz"},
        ],
    )
    _write_csv(
        stage2_manifest,
        [
            {"ligand_id": "ligand_mismatch", "trajectory_npz": "mismatch.npz"},
            {"ligand_id": "ligand_near", "trajectory_npz": "near.npz"},
        ],
    )

    payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=2,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=False,
        out_md=str(tmp_path / "runner.md"),
    )

    summary = payload["summary"]
    assert summary["source_lane_candidate_count"] == 2
    assert summary["strict_band_candidate_count"] == 0
    assert summary["near_band_candidate_count"] == 1
    assert summary["other_band_candidate_count"] == 1
    assert summary["filtered_lane_candidate_count"] == 1
    assert summary["selected_lane_candidate_count"] == 1
    assert summary["top_k_requested"] == 2
    assert summary["top_k_effective"] == 1
    assert summary["top_k_shortfall_count"] == 1
    assert summary["top_k_shortfall_reason"] == (
        "filtered_lane_candidate_count=1 below requested_top_k=2 after strict_then_near_fill"
    )
    assert summary["rescue_review_band_mismatch_count"] == 1
    assert summary["source_rescue_review_band_mismatch_count"] == 1
    assert summary["filtered_rescue_review_band_mismatch_count"] == 0
    assert summary["selected_rescue_review_band_mismatch_count"] == 0
    assert summary["rescue_review_band_consistency_counts"] == {
        "match": 1,
        "mismatch_fail_closed": 1,
    }
    assert [row["ligand_id"] for row in payload["rows"]] == ["ligand_near"]
    assert payload["rows"][0]["rescue_review_band_consistency_status"] == "match"
    assert payload["rows"][0]["numeric_rescue_review_bucket"] == "near"


def test_run_wetlab_tcruzi_pde_allatom_rescue_execute_reads_flat_scoring_summary(
    tmp_path: Path, monkeypatch
) -> None:
    lane_json, claim_json, equivalence_json = _write_single_ready_rescue_inputs(tmp_path)
    captured_cmd: list[str] = []

    class Result:
        returncode = 0

    def fake_scoring_run(cmd: list[str], **_: object) -> Result:
        captured_cmd[:] = cmd
        out_summary_json = Path(cmd[cmd.index("--out-summary-json") + 1])
        out_scores_csv = Path(cmd[cmd.index("--out-scores-csv") + 1])
        out_summary_json.parent.mkdir(parents=True, exist_ok=True)
        out_scores_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_json(
            out_summary_json,
            {
                "queue_rows": 1,
                "processed_jobs": 1,
                "avg_binding_energy_proxy": -9.25,
                "avg_stability_score": 0.86,
            },
        )
        out_scores_csv.write_text("ligand_id\nligand_strict\n", encoding="utf-8")
        return Result()

    monkeypatch.setattr("tools.run_wetlab_tcruzi_pde_allatom_rescue.subprocess.run", fake_scoring_run)

    payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=1,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=True,
        out_md=str(tmp_path / "runner.md"),
    )

    summary = payload["summary"]
    assert summary["execution_mode"] == "pseudo_allatom_backmapping_scoring_executed"
    assert summary["rescue_execution_plan_status"] == "execute_requested"
    assert summary["scoring_status"] == "pass"
    assert summary["scoring_status_reason"] == "processed_jobs_complete"
    assert summary["scoring_summary_present"] is True
    assert summary["scoring_expected_jobs"] == 1
    assert summary["processed_jobs"] == 1
    assert summary["avg_binding_energy_proxy"] == -9.25
    assert summary["avg_stability_score"] == 0.86
    attempt_dir = Path(summary["attempt_dir"])
    for option in [
        "--queue-csv",
        "--stage2-manifest-csv",
        "--out-dir",
        "--out-scores-csv",
        "--out-summary-json",
        "--out-summary-md",
    ]:
        resolved_path = Path(captured_cmd[captured_cmd.index(option) + 1])
        assert resolved_path == attempt_dir or resolved_path.is_relative_to(attempt_dir)
    assert payload["rows"][0]["rescue_execution_status"] == "execute_requested"
    assert payload["rows"][0]["rescue_iteration_metadata"]["execute_requested"] is True


def test_run_wetlab_tcruzi_pde_allatom_rescue_passes_clash_relief_flags(
    tmp_path: Path, monkeypatch
) -> None:
    lane_json, claim_json, equivalence_json = _write_single_ready_rescue_inputs(tmp_path)
    captured_cmd: list[str] = []

    class Result:
        returncode = 0

    def fake_scoring_run(cmd: list[str], **_: object) -> Result:
        captured_cmd[:] = cmd
        out_summary_json = Path(cmd[cmd.index("--out-summary-json") + 1])
        out_scores_csv = Path(cmd[cmd.index("--out-scores-csv") + 1])
        out_summary_json.parent.mkdir(parents=True, exist_ok=True)
        out_scores_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_json(
            out_summary_json,
            {
                "queue_rows": 1,
                "processed_jobs": 1,
                "avg_binding_energy_proxy": -0.08,
                "avg_stability_score": 0.66,
                "clash_relief_mode": "translate",
                "avg_pre_repair_binding_energy_proxy": 0.113,
                "avg_pre_repair_mean_min_distance_A": 0.672,
                "avg_clash_relief_frame_fraction": 1.0,
                "avg_clash_relief_mean_translation_A": 1.45,
            },
        )
        out_scores_csv.write_text("ligand_id\nligand_strict\n", encoding="utf-8")
        return Result()

    monkeypatch.setattr("tools.run_wetlab_tcruzi_pde_allatom_rescue.subprocess.run", fake_scoring_run)

    payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=1,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=True,
        out_md=str(tmp_path / "runner.md"),
        clash_relief_mode="translate",
        clash_relief_target_min_distance_A=2.12,
        clash_relief_max_translation_A=2.0,
        clash_relief_max_steps=12,
    )

    assert captured_cmd[captured_cmd.index("--clash-relief-mode") + 1] == "translate"
    assert captured_cmd[captured_cmd.index("--clash-relief-target-min-distance-A") + 1] == "2.12"
    assert captured_cmd[captured_cmd.index("--clash-relief-max-translation-A") + 1] == "2.0"
    assert captured_cmd[captured_cmd.index("--clash-relief-max-steps") + 1] == "12"
    summary = payload["summary"]
    assert summary["clash_relief_mode"] == "translate"
    assert summary["avg_pre_repair_binding_energy_proxy"] == 0.113
    assert summary["avg_clash_relief_frame_fraction"] == 1.0


def test_run_wetlab_tcruzi_pde_allatom_rescue_records_deterministic_attempt_fingerprint(
    tmp_path: Path,
) -> None:
    lane_json, claim_json, equivalence_json = _write_single_ready_rescue_inputs(tmp_path)

    first_payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=1,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=False,
        out_md=str(tmp_path / "runner_first.md"),
    )
    second_payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=1,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=False,
        out_md=str(tmp_path / "runner_second.md"),
    )

    summary = first_payload["summary"]
    second_summary = second_payload["summary"]
    assert summary["input_fingerprint_sha256"] == second_summary["input_fingerprint_sha256"]
    assert len(summary["input_fingerprint_sha256"]) == 64
    assert summary["attempt_id"] != second_summary["attempt_id"]
    assert summary["attempt_id"].startswith(f"inputfp_{summary['input_fingerprint_sha256'][:12]}__noexec__")
    assert second_summary["attempt_id"].startswith(f"inputfp_{summary['input_fingerprint_sha256'][:12]}__noexec__")
    assert summary["attempt_sequence"] >= 1
    assert second_summary["attempt_sequence"] == summary["attempt_sequence"] + 1
    assert summary["attempt_id_source"] == "deterministic_input_fingerprint_sequence"
    assert second_summary["attempt_id_source"] == "deterministic_input_fingerprint_sequence"
    assert summary["current_artifact_is_pointer"] is True
    assert summary["attempt_dir"].endswith(f"/attempts/{summary['attempt_id']}")
    assert second_summary["attempt_dir"].endswith(f"/attempts/{second_summary['attempt_id']}")

    ledger = first_payload["input_fingerprint_ledger"]
    assert first_payload["input_fingerprints"] == ledger
    assert ledger["schema_version"] == "pde_allatom_rescue_input_fingerprint_v1"
    for key in [
        "lane_json",
        "stage1_queue_csv",
        "stage2_manifest_csv",
        "claim_readiness_json",
        "equivalence_gate_json",
    ]:
        assert ledger[key]["present"] is True
        assert ledger[key]["size"] > 0
        assert len(ledger[key]["sha256"]) == 64
    assert ledger["selected_stage2_trajectory_files"] == [
        {
            "ligand_id": "ligand_strict",
            "trajectory_npz": "strict.npz",
            "path": str(tmp_path / "traj" / "strict.npz"),
            "present": True,
            "size": len(b"strict trajectory"),
            "sha256": ledger["selected_stage2_trajectory_files"][0]["sha256"],
        }
    ]
    assert len(ledger["selected_stage2_trajectory_files"][0]["sha256"]) == 64

    attempt_state_json = Path(summary["attempt_state_json"])
    second_attempt_state_json = Path(second_summary["attempt_state_json"])
    current_state_json = Path(summary["allatom_state_json"])
    assert attempt_state_json.exists()
    assert second_attempt_state_json.exists()
    assert current_state_json.exists()
    assert json.loads(attempt_state_json.read_text(encoding="utf-8")) == first_payload
    assert json.loads(second_attempt_state_json.read_text(encoding="utf-8")) == second_payload
    assert json.loads(current_state_json.read_text(encoding="utf-8")) == second_payload
    for key in ["manifest_csv", "queue_csv", "stage2_manifest_csv", "state_json"]:
        artifact_path = Path(summary["attempt_artifacts"][key])
        assert artifact_path.is_relative_to(Path(summary["attempt_dir"]))
        assert artifact_path.exists()
    assert first_payload["rows"][0]["attempt_id"] == summary["attempt_id"]
    assert first_payload["rows"][0]["input_fingerprint_sha256"] == summary["input_fingerprint_sha256"]


def test_run_wetlab_tcruzi_pde_allatom_rescue_execute_marks_incomplete_flat_summary(
    tmp_path: Path, monkeypatch
) -> None:
    lane_json, claim_json, equivalence_json = _write_single_ready_rescue_inputs(tmp_path)

    class Result:
        returncode = 0

    def fake_scoring_run(cmd: list[str], **_: object) -> Result:
        out_summary_json = Path(cmd[cmd.index("--out-summary-json") + 1])
        out_summary_json.parent.mkdir(parents=True, exist_ok=True)
        _write_json(out_summary_json, {"queue_rows": 1, "processed_jobs": 0})
        return Result()

    monkeypatch.setattr("tools.run_wetlab_tcruzi_pde_allatom_rescue.subprocess.run", fake_scoring_run)

    payload = run(
        lane_json=str(lane_json),
        target_id="T. cruzi PDE",
        shard_id="20_of_20",
        top_k=1,
        filter_mode="strict_then_near_fill",
        claim_readiness_json=str(claim_json),
        equivalence_gate_json=str(equivalence_json),
        python_bin=sys.executable,
        execute=True,
        out_md=str(tmp_path / "runner.md"),
    )

    summary = payload["summary"]
    assert summary["scoring_status"] == "incomplete"
    assert summary["scoring_status_reason"] == "processed_jobs=0 below expected_jobs=1"
    assert summary["scoring_summary_present"] is True
    assert summary["scoring_expected_jobs"] == 1
    assert summary["processed_jobs"] == 0
