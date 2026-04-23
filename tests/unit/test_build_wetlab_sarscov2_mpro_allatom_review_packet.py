from __future__ import annotations

import json
from pathlib import Path

from tools.build_wetlab_sarscov2_mpro_allatom_review_packet import build_payload


def test_build_wetlab_sarscov2_mpro_allatom_review_packet(tmp_path: Path) -> None:
    scoring_json = tmp_path / "summary.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {"ligand_id": "lig_m", "queue_id": "qm", "mean_min_distance_A": 2.3, "binding_energy_proxy": -1.5, "binding_energy_mmpbsa_kcal_mol_proxy": -1.5, "binding_energy_mmpbsa_std": 0.11, "stability_score": 0.41, "contact_fraction": 0.64, "trajectory_frames": 220, "ligand_model": "3bead_implicit_hbond", "backmapped_pdb": "m.pdb", "score_json": "m.json"},
                    {"ligand_id": "lig_n", "queue_id": "qn", "mean_min_distance_A": 3.2, "binding_energy_proxy": -1.1, "binding_energy_mmpbsa_kcal_mol_proxy": -1.1, "binding_energy_mmpbsa_std": 0.2, "stability_score": 0.3, "contact_fraction": 0.5, "trajectory_frames": 180, "ligand_model": "3bead_implicit_hbond", "backmapped_pdb": "n.pdb", "score_json": "n.json"},
                ]
            }
        ),
        encoding="utf-8",
    )
    lane_payload = {"summary": {"source_shard_id": "02_of_20", "selected_command_kind": "pseudo_allatom_local_refine", "selected_threshold_A": 2.5, "selected_ligand_model": "3bead_implicit_hbond"}}
    runner_payload = {"summary": {"allatom_summary_json": str(scoring_json), "scoring_status": "pass", "execution_mode": "pseudo_allatom_backmapping_scoring_executed"}}
    payload = build_payload(lane_payload, runner_payload)
    assert payload["summary"]["under_2p5_candidate_count"] == 1
    assert payload["summary"]["near_candidate_count"] == 0
    assert payload["summary"]["best_ligand_id"] == "lig_m"

