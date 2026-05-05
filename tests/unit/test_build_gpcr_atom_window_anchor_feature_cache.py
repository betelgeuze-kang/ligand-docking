from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from tools import build_gpcr_atom_window_anchor_feature_cache as mod


def _pdb_atom(record: str, serial: int, atom: str, resn: str, chain: str, resi: int, x: float, y: float, z: float) -> str:
    return (
        f"{record:<6}{serial:5d} {atom:^4s} {resn:>3s} {chain:1s}{resi:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           {atom[0]:>2s}"
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_cache_materializes_direct_atom_window_features(tmp_path: Path) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.5, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.0, 0.0, 3.0),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.5, 0.0, 3.0),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.0, 0.5, 3.0),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.5, 0.5, 3.0),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.0, 0.0, 3.5),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    npz = tmp_path / "traj.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray(
            [
                [[0.0, 0.0, 3.0]],
                [[0.0, 0.0, 4.0]],
                [[0.0, 0.0, 2.0]],
            ],
            dtype=np.float32,
        ),
        protein_atom_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    scores = tmp_path / "scores.csv"
    _write_csv(
        scores,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pos",
                "is_binder": "1",
                "binding_score_composite_v7": "-2.0",
                "protein_structure_source_path": str(pdb),
                "trajectory_npz": str(npz),
            }
        ],
    )

    rows, summary = mod.build_cache(input_csv=scores, target="CHEMBL217_DRD2_HUMAN", top_n=1)

    assert summary["selected_row_count"] == 1
    assert summary["available_feature_count"] == 1
    assert rows[0]["class_a_atom_anchor_available"] == 1
    assert rows[0]["class_a_atom_anchor_min_distance_A"] == 2.0
    assert rows[0]["class_a_atom_anchor_contact_fraction_le_2p8A"] == 1 / 3
    assert rows[0]["class_a_atom_anchor_contact_fraction_2p8_4p2A"] == 2 / 3


def test_build_cache_uses_labels_csv_when_scores_lack_binder_column(tmp_path: Path) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.5, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.0, 0.0, 3.0),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.5, 0.0, 3.0),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.0, 0.5, 3.0),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.5, 0.5, 3.0),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.0, 0.0, 3.5),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    npz = tmp_path / "traj.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 3.0]]], dtype=np.float32),
        protein_atom_frames=np.asarray([[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]]], dtype=np.float32),
    )
    scores = tmp_path / "scores.csv"
    _write_csv(
        scores,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy",
                "binding_score_composite_v7": "-9.0",
                "protein_structure_source_path": str(pdb),
                "trajectory_npz": str(npz),
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "pos",
                "binding_score_composite_v7": "-1.0",
                "protein_structure_source_path": str(pdb),
                "trajectory_npz": str(npz),
            },
        ],
    )
    labels = tmp_path / "labels.csv"
    _write_csv(
        labels,
        [
            {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "pos", "is_binder": "1"},
            {"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "decoy", "is_binder": "0"},
        ],
    )

    rows, summary = mod.build_cache(
        input_csv=scores,
        labels_csv=labels,
        target="CHEMBL217_DRD2_HUMAN",
        top_n=1,
        include_positives=True,
    )

    assert summary["positive_label_key_count"] == 1
    assert summary["selected_row_count"] == 2
    assert [row["ligand_id"] for row in rows] == ["decoy", "pos"]
