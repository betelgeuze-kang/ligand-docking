from __future__ import annotations

from tools.wetlab.build_wetlab_tcruzi_pde_ligand_atomization_gap_packet import build_payload


def test_ligand_atomization_gap_packet_blocks_two_bead_ligands() -> None:
    payload = build_payload(
        {
            "rows": [
                {
                    "ligand_id": "two_bead_hit",
                    "ligand_smiles": "CCOc1ccccc1",
                    "source_pool_class": "external_homolog_pdeb1_geomstab_rescore",
                    "binding_energy_proxy": -0.70,
                    "mean_min_distance_A": 3.5,
                    "stability_score": 0.001,
                    "backmapped_ligand_atoms": 2,
                    "backmapped_pdb": "hit.pdb",
                    "score_json": "hit.json",
                    "trajectory_npz": "hit.npz",
                },
                {
                    "ligand_id": "atomized_hit",
                    "ligand_smiles": "CCO",
                    "source_pool_class": "external_bindingdb_similarity_seed",
                    "binding_energy_proxy": -0.60,
                    "mean_min_distance_A": 4.0,
                    "stability_score": 0.001,
                    "backmapped_ligand_atoms": 3,
                    "backmapped_pdb": "atomized.pdb",
                    "score_json": "atomized.json",
                    "trajectory_npz": "atomized.npz",
                },
            ]
        },
        source_queue_json="queue.json",
    )

    summary = payload["summary"]
    assert summary["queue_row_count"] == 2
    assert summary["atomization_ready_count"] == 1
    assert summary["atomization_blocked_count"] == 1
    assert summary["commercial_gap_status"] == "blocked_ligand_atomization_gap"
    assert summary["claim_promotion_allowed"] is False
    assert summary["worst_gap_ligand_id"] == "two_bead_hit"

    rows = {row["ligand_id"]: row for row in payload["rows"]}
    assert rows["two_bead_hit"]["expected_ligand_heavy_atom_count_from_smiles"] == 9
    assert rows["two_bead_hit"]["observed_backmapped_ligand_atom_count"] == 2
    assert rows["two_bead_hit"]["atomization_status"] == "blocked_ligand_atomization_gap"
    assert rows["two_bead_hit"]["metric_policy"] == (
        "do_not_treat_two_bead_ligand_backmaps_as_all_atom_pose_preservation"
    )
    assert rows["atomized_hit"]["atomization_status"] == "atomization_ready_for_pose_metric_preflight"
