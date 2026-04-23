from __future__ import annotations

import json
from pathlib import Path

from tools.build_wetlab_cathepsin_k_allatom_review_packet import build_payload


def test_build_wetlab_cathepsin_k_allatom_review_packet(tmp_path: Path) -> None:
    scoring_json = tmp_path / "summary.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {"ligand_id": "lig_a", "queue_id": "qa", "mean_min_distance_A": 2.1, "binding_energy_proxy": -1.2, "binding_energy_mmpbsa_kcal_mol_proxy": -1.2, "binding_energy_mmpbsa_std": 0.1, "stability_score": 0.4, "contact_fraction": 0.6, "trajectory_frames": 200, "ligand_model": "3bead_implicit_hbond", "backmapped_pdb": "a.pdb", "score_json": "a.json"},
                    {"ligand_id": "lig_b", "queue_id": "qb", "mean_min_distance_A": 2.7, "binding_energy_proxy": -1.0, "binding_energy_mmpbsa_kcal_mol_proxy": -1.0, "binding_energy_mmpbsa_std": 0.2, "stability_score": 0.3, "contact_fraction": 0.5, "trajectory_frames": 180, "ligand_model": "3bead_implicit_hbond", "backmapped_pdb": "b.pdb", "score_json": "b.json"},
                ]
            }
        ),
        encoding="utf-8",
    )
    lane_payload = {"summary": {"source_shard_id": "19_of_20", "selected_command_kind": "pseudo_allatom_local_refine", "selected_threshold_A": 2.5, "selected_ligand_model": "3bead_implicit_hbond"}}
    runner_payload = {"summary": {"allatom_summary_json": str(scoring_json), "scoring_status": "pass", "execution_mode": "pseudo_allatom_backmapping_scoring_executed"}}
    payload = build_payload(lane_payload, runner_payload)
    summary = payload["summary"]
    assert summary["promoted_candidate_count"] == 2
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["near_candidate_count"] == 1
    assert summary["best_ligand_id"] == "lig_a"
    assert summary["claim_gate_requirement_mode"] == "optional"
    assert summary["claim_gate_status"] == "claim_optional_unavailable"
    assert summary["claim_gate_required_for_final_wetlab"] is False
    assert summary["wetlab_final_gate_pass"] is True
    assert summary["commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["commercial_hard_gate_pass_v1"] is True
    assert summary["commercial_decision_class_v1"] == "commercial_wetlab_ready"
    assert summary["commercial_risk_bucket_v1"] == "low"
    assert summary["commercial_soft_score_v1"] > 90.0
    assert summary["commercial_confidence_score_v1"] >= 80.0
    assert summary["commercial_claim_requirement_mode_v2"] == "optional"
    assert payload["rows"][0]["commercial_hard_gate_pass_v1"] is True
    assert payload["rows"][0]["commercial_decision_class_v1"] == "commercial_wetlab_ready"
