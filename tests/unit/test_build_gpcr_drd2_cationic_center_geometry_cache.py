from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import build_gpcr_drd2_cationic_center_geometry_cache as mod

ROOT = Path(__file__).resolve().parents[2]


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


def test_cationic_center_cache_measures_basic_amine_to_acidic_anchor(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.4, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.2, 0.0, 3.1),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.3, 0.0, 3.2),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.2, 0.2, 3.1),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.3, 0.2, 3.2),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.2, 0.0, 3.5),
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
                [[0.2, 0.0, 3.2], [10.0, 0.0, 0.0]],
                [[0.2, 0.0, 3.4], [10.0, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
        protein_atom_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
        ligand_basic_amine_atom_indices=np.asarray([0], dtype=np.int32),
    )
    input_csv = tmp_path / "rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "trajectory_npz": str(npz),
                "protein_structure_source_path": str(pdb),
            }
        ],
    )

    rows, summary = mod.build_cache(input_csv=input_csv, generated_at_local="2026-05-05T00:00:00+09:00")

    assert summary["available_feature_count"] == 1
    assert summary["positive_available"] is True
    assert rows[0]["class_a_cationic_center_available"] == 1
    assert rows[0]["class_a_cationic_center_basic_atom_count"] == 1
    assert rows[0]["class_a_cationic_center_anchor_atom_count"] == 2
    assert np.isclose(rows[0]["class_a_cationic_center_mean_distance_A"], 3.3)
    assert rows[0]["class_a_cationic_center_contact_fraction_2p8_4p2A"] == 1.0
    assert rows[0]["class_a_cationic_center_contact_fraction_le_2p8A"] == 0.0


def test_cationic_center_cache_uses_static_anchor_when_prod_light_npz_omits_protein_frames(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.4, 0.0, 0.0),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    npz = tmp_path / "prod_light.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray([[[0.2, 0.0, 3.2], [10.0, 0.0, 0.0]]], dtype=np.float32),
        ligand_backmapping_static_anchor_coords=np.asarray([[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]], dtype=np.float32),
        ligand_basic_amine_atom_indices=np.asarray([0], dtype=np.int32),
    )
    input_csv = tmp_path / "rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "trajectory_npz": str(npz),
                "protein_structure_source_path": str(pdb),
            }
        ],
    )

    rows, summary = mod.build_cache(input_csv=input_csv, generated_at_local="2026-05-05T00:00:00+09:00")

    assert summary["available_feature_count"] == 1
    assert rows[0]["class_a_cationic_center_available"] == 1
    assert rows[0]["class_a_cationic_center_anchor_atom_count"] == 2
    assert np.isclose(rows[0]["class_a_cationic_center_mean_distance_A"], 3.2)


def test_cationic_center_cache_cli_writes_outputs(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.4, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.2, 0.0, 3.1),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.3, 0.0, 3.2),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.2, 0.2, 3.1),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.3, 0.2, 3.2),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.2, 0.0, 3.5),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    npz = tmp_path / "traj.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray([[[0.2, 0.0, 3.2]]], dtype=np.float32),
        protein_atom_frames=np.asarray([[[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]]], dtype=np.float32),
        ligand_basic_amine_atom_indices=np.asarray([0], dtype=np.int32),
    )
    input_csv = tmp_path / "rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "trajectory_npz": str(npz),
                "protein_structure_source_path": str(pdb),
            }
        ],
    )
    out_csv = tmp_path / "cache.csv"
    out_json = tmp_path / "cache.json"
    out_md = tmp_path / "cache.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_cationic_center_geometry_cache.py"),
            "--input-csv",
            str(input_csv),
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["available_feature_count"] == 1
    assert "class_a_cationic_center_available" in out_csv.read_text(encoding="utf-8")
    assert "GPCR DRD2 Cationic-Center Geometry Cache" in out_md.read_text(encoding="utf-8")
