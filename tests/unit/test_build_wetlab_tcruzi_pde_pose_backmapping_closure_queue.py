from __future__ import annotations

import csv
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_pose_backmapping_closure_queue import build_payload


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_pose_backmapping_queue_dedupes_energy_hits_and_keeps_claim_locked(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_pdeb1_seed_screen" / "stage3_scores.csv",
        [
            {
                "queue_id": "seed_a",
                "target": "T. cruzi PDE",
                "ligand_id": "shared_hit",
                "ligand_smiles": "CCO",
                "binding_energy_proxy": "-0.70",
                "mean_min_distance_A": "3.90",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_npz": "runs/shared_hit.npz",
                "backmapped_pdb": "",
                "score_json": "",
            },
            {
                "queue_id": "seed_b",
                "target": "T. cruzi PDE",
                "ligand_id": "weak_not_energy_hit",
                "ligand_smiles": "CCC",
                "binding_energy_proxy": "-0.20",
                "mean_min_distance_A": "2.80",
                "stability_score": "0.40",
                "contact_fraction": "0.60",
                "trajectory_npz": "",
                "backmapped_pdb": "",
                "score_json": "",
            },
        ],
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_external_geomstab_rescore_3bead_current" / "stage3_scores.csv",
        [
            {
                "queue_id": "rescore_a",
                "target": "T. cruzi PDE",
                "ligand_id": "shared_hit",
                "ligand_smiles": "CCO",
                "binding_energy_proxy": "-0.65",
                "mean_min_distance_A": "3.70",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_npz": "runs/shared_hit_rescore.npz",
                "backmapped_pdb": "runs/shared_hit.pdb",
                "score_json": "runs/shared_hit_score.json",
            }
        ],
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" / "stage9_stage3_scores.csv",
        [
            {
                "queue_id": "bindingdb_a",
                "target": "T. cruzi PDE",
                "ligand_id": "bindingdb_hit",
                "ligand_smiles": "CCN",
                "binding_energy_proxy": "-0.60",
                "mean_min_distance_A": "4.35",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_npz": "runs/bindingdb_hit.npz",
                "backmapped_pdb": "",
                "score_json": "",
            }
        ],
    )
    _write_csv(
        tmp_path / "runs" / "wetlab_tcruzi_pde_bindingdb_similarity_seed_screen" / "stage_stage3_scores.csv",
        [
            {
                "queue_id": "pilot",
                "target": "T. cruzi PDE",
                "ligand_id": "pilot_hit",
                "ligand_smiles": "CCF",
                "binding_energy_proxy": "-0.80",
                "mean_min_distance_A": "4.80",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
                "trajectory_npz": "",
                "backmapped_pdb": "",
                "score_json": "",
            }
        ],
    )

    payload = build_payload(
        root=tmp_path,
        translation_evidence_payload={
            "summary": {
                "translation_score_candidate_row_count": 3,
                "translation_energy_pass_count": 3,
                "translation_core_pass_count": 0,
            }
        },
        metric_scale_payload={"summary": {"metric_scale_gap_detected": True}},
    )

    summary = payload["summary"]
    assert summary["status"] == "pose_backmapping_closure_queue_ready"
    assert summary["energy_hit_unique_ligand_count"] == 2
    assert summary["queue_row_count"] == 2
    assert summary["translation_core_pass_count"] == 0
    assert summary["metric_scale_gap_detected"] is True
    assert summary["claim_promotion_allowed"] is False

    rows = payload["rows"]
    assert [row["ligand_id"] for row in rows] == ["shared_hit", "bindingdb_hit"]
    assert rows[0]["closure_lane"] == "measure_pose_backmapping_and_local_min_survival"
    assert rows[1]["closure_lane"] == "rebuild_backmapped_pose_then_measure_pose_backmapping"
    assert rows[0]["required_measurements"] == (
        "pose_preservation_rmsd_A;backmapping_consistency_score;"
        "local_minimization_survival_fraction;replicate_pass_fraction"
    )
    assert rows[0]["threshold_policy"] == "do_not_relax_energy_distance_or_stability_thresholds"
