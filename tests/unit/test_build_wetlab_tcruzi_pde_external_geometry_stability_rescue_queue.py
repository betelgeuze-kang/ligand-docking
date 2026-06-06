from __future__ import annotations

import csv
from pathlib import Path

from tools.wetlab.build_wetlab_tcruzi_pde_external_geometry_stability_rescue_queue import build_payload


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_external_geometry_stability_rescue_queue_prioritizes_energy_hits(tmp_path: Path) -> None:
    queue_csv = tmp_path / "stage1_queue.csv"
    scores_csv = tmp_path / "stage3_scores.csv"
    base_cols = {
        "queue_id": "",
        "target": "T. cruzi PDE",
        "replica_idx": "0",
        "ligand_id": "",
        "ligand_smiles": "CCO",
        "ligand_source": "csv",
        "ligand_mw": "100",
        "ligand_logp": "1.0",
        "ligand_h_donors": "1",
        "ligand_h_acceptors": "1",
        "ligand_rot_bonds": "1",
        "ligand_bead_count": "2",
        "pocket_x": "0",
        "pocket_y": "0",
        "pocket_z": "0",
    }
    _write_csv(
        queue_csv,
        [
            {**base_cols, "queue_id": "q_stability", "ligand_id": "stability_only"},
            {**base_cols, "queue_id": "q_both", "ligand_id": "distance_and_stability"},
            {**base_cols, "queue_id": "q_weak", "ligand_id": "weak_energy"},
        ],
    )
    _write_csv(
        scores_csv,
        [
            {
                "target": "T. cruzi PDE",
                "ligand_id": "distance_and_stability",
                "binding_energy_proxy": "-0.80",
                "mean_min_distance_A": "3.8",
                "stability_score": "0.001",
                "contact_fraction": "0.01",
            },
            {
                "target": "T. cruzi PDE",
                "ligand_id": "stability_only",
                "binding_energy_proxy": "-0.70",
                "mean_min_distance_A": "3.05",
                "stability_score": "0.02",
                "contact_fraction": "0.05",
            },
            {
                "target": "T. cruzi PDE",
                "ligand_id": "weak_energy",
                "binding_energy_proxy": "-0.20",
                "mean_min_distance_A": "2.8",
                "stability_score": "0.6",
                "contact_fraction": "0.7",
            },
        ],
    )

    payload = build_payload(
        stage1_queue_csv=queue_csv.as_posix(),
        stage3_scores_csv=scores_csv.as_posix(),
    )

    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "external_geometry_stability_rescue_queue_ready"
    assert summary["energy_pass_candidate_count"] == 2
    assert summary["rescue_row_count"] == 2
    assert summary["core_pass_count"] == 0
    assert summary["stability_only_count"] == 1
    assert summary["distance_and_stability_count"] == 1
    assert summary["top_rescue_ligand_id"] == "stability_only"
    assert summary["claim_promotion_allowed"] is False
    assert rows[0]["core_gate_blocker"] == "stability_only"
    assert rows[0]["recommended_rescue_mode"] == "replicate_stability_rescue"
    assert rows[0]["recommended_rescore_model"] == "3bead_implicit_hbond"
    assert rows[0]["translation_energy_pass"] is True
    assert rows[0]["translation_core_pass"] is False
    assert rows[0]["rescue_queue_id"] == "q_stability__geomstab_rescue_r01"
    assert rows[1]["core_gate_blocker"] == "distance_and_stability"
