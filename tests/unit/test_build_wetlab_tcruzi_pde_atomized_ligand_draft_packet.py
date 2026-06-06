from __future__ import annotations

from pathlib import Path

from tools.wetlab.build_wetlab_tcruzi_pde_atomized_ligand_draft_packet import build_payload


def _write_anchor_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "MODEL        1",
                "ATOM      1 C1  LIG L   1       0.000   0.000   0.000  1.00 30.00           C",
                "ATOM      2 C2  LIG L   1       3.000   0.000   0.000  1.00 30.00           C",
                "ENDMDL",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_atomized_ligand_draft_packet_generates_claim_locked_rdkit_outputs(tmp_path: Path) -> None:
    anchor_pdb = tmp_path / "anchor.pdb"
    _write_anchor_pdb(anchor_pdb)
    payload = build_payload(
        {
            "rows": [
                {
                    "ligand_id": "ethanol_seed",
                    "ligand_smiles": "CCO",
                    "source_pool_class": "external_bindingdb_similarity_seed",
                    "binding_energy_proxy": -0.6,
                    "expected_ligand_heavy_atom_count_from_smiles": 3,
                    "backmapped_pdb": anchor_pdb.as_posix(),
                    "trajectory_npz": "traj.npz",
                }
            ]
        },
        source_gap_json="gap.json",
        out_dir=tmp_path / "drafts",
    )

    summary = payload["summary"]
    assert summary["row_count"] == 1
    assert summary["atomization_draft_ready_count"] == 1
    assert summary["two_point_anchor_oriented_count"] == 1
    assert summary["parameterization_ready_count"] == 0
    assert summary["claim_promotion_allowed"] is False

    row = payload["rows"][0]
    assert row["atomized_ligand_heavy_atom_count"] == 3
    assert row["atomization_draft_ready"] is True
    assert row["anchor_status"] == "oriented_to_two_point_pseudo_anchor"
    assert row["parameterization_status"] == "pending"
    assert row["claim_policy"] == "atomized_ligand_draft_only_not_pose_preservation_or_local_min_survival_evidence"
    assert Path(row["atomized_ligand_sdf"]).exists()
    assert Path(row["atomized_ligand_pdb"]).exists()
