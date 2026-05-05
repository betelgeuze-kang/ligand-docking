from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import repair_gpcr_drd2_pseudo_allatom_backmapping as mod

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


def test_build_repair_expands_two_bead_drd2_positive_to_pseudo_allatom_npz(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.6, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.2, 0.0, 3.0),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.4, 0.0, 3.1),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.2, 0.2, 3.0),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.4, 0.2, 3.1),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.2, 0.0, 3.4),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_npz = tmp_path / "source.npz"
    ligand_frames = np.asarray(
        [
            [[0.3, 0.0, 3.0], [0.3, 0.0, 4.2]],
            [[0.3, 0.1, 3.0], [0.3, 0.1, 4.2]],
        ],
        dtype=np.float32,
    )
    protein_atom_frames = np.asarray(
        [
            [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]],
            [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]],
        ],
        dtype=np.float32,
    )
    np.savez(source_npz, ligand_frames=ligand_frames, protein_atom_frames=protein_atom_frames)
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
                "trajectory_npz": str(source_npz),
                "protein_structure_source_path": str(pdb),
            }
        ],
    )

    payload, rows = mod.build_repair(
        input_csv=input_csv,
        out_root=tmp_path / "repaired",
        generated_at_local="2026-05-05T00:00:00+09:00",
    )

    assert payload["summary"]["status"] == "pseudo_allatom_repair_ready"
    assert payload["summary"]["claim_promotion_allowed"] is False
    row = rows[0]
    assert row["allatom_backmapping_status"] == "ok"
    assert int(row["source_ligand_frame_atom_count"]) == 2
    assert int(row["repaired_ligand_frame_atom_count"]) > 2
    assert float(row["allatom_backmapping_coverage_ratio"]) == 1.0
    assert int(row["allatom_basic_amine_atom_count"]) >= 1
    assert int(row["allatom_anchor_atom_count"]) == 2
    assert np.isclose(float(row["target_cation_anchor_distance_A_mean"]), 3.2, atol=1e-5)
    with np.load(str(row["trajectory_npz"]), allow_pickle=False) as npz:
        repaired_frames = np.asarray(npz["ligand_frames"])
        original_frames = np.asarray(npz["ligand_coarse_frames_original"])
        basic_indices = np.asarray(npz["ligand_basic_amine_atom_indices"])
    assert repaired_frames.shape[0] == ligand_frames.shape[0]
    assert repaired_frames.shape[1] == int(row["repaired_ligand_frame_atom_count"])
    assert original_frames.shape == ligand_frames.shape
    assert basic_indices.shape[0] >= 1


def test_repair_cli_writes_manifest_outputs(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.6, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.2, 0.0, 3.0),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.4, 0.0, 3.1),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.2, 0.2, 3.0),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.4, 0.2, 3.1),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.2, 0.0, 3.4),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_npz = tmp_path / "source.npz"
    np.savez(
        source_npz,
        ligand_frames=np.asarray([[[0.3, 0.0, 3.0], [0.3, 0.0, 4.2]]], dtype=np.float32),
        protein_atom_frames=np.asarray([[[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]]], dtype=np.float32),
    )
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
                "trajectory_npz": str(source_npz),
                "protein_structure_source_path": str(pdb),
            }
        ],
    )
    out_json = tmp_path / "repair.json"
    out_csv = tmp_path / "repair.csv"
    out_md = tmp_path / "repair.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/repair_gpcr_drd2_pseudo_allatom_backmapping.py"),
            "--input-csv",
            str(input_csv),
            "--out-root",
            str(tmp_path / "out"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
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
    assert payload["summary"]["status"] == "pseudo_allatom_repair_ready"
    assert "GPCR DRD2 Pseudo-Allatom Backmapping Repair" in out_md.read_text(encoding="utf-8")
    assert "pseudo_allatom_backmapping_generated" in out_csv.read_text(encoding="utf-8")


def test_positive_only_anchor_mode_does_not_force_basic_decoy_to_anchor(tmp_path: Path) -> None:
    pdb = tmp_path / "drd2.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.6, 0.0, 0.0),
                _pdb_atom("HETATM", 3, "C1", "LIG", "A", 900, 0.2, 0.0, 3.0),
                _pdb_atom("HETATM", 4, "C2", "LIG", "A", 900, 0.4, 0.0, 3.1),
                _pdb_atom("HETATM", 5, "C3", "LIG", "A", 900, 0.2, 0.2, 3.0),
                _pdb_atom("HETATM", 6, "C4", "LIG", "A", 900, 0.4, 0.2, 3.1),
                _pdb_atom("HETATM", 7, "C5", "LIG", "A", 900, 0.2, 0.0, 3.4),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_npz = tmp_path / "source.npz"
    np.savez(
        source_npz,
        ligand_frames=np.asarray(
            [
                [[0.3, 0.0, 3.0], [0.3, 0.0, 4.2]],
                [[0.3, 0.1, 3.0], [0.3, 0.1, 4.2]],
            ],
            dtype=np.float32,
        ),
        protein_atom_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.6, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )
    input_csv = tmp_path / "repair_rows.csv"
    common = {
        "target": "CHEMBL217_DRD2_HUMAN",
        "ligand_smiles": "CNCCc1ccccc1",
        "trajectory_npz": str(source_npz),
        "protein_structure_source_path": str(pdb),
    }
    _write_csv(
        input_csv,
        [
            {"ligand_id": "decoy_basic", "is_positive": "False", **common},
            {"ligand_id": "CHEMBL301265", "is_positive": "True", **common},
        ],
    )

    _payload, rows = mod.build_repair(
        input_csv=input_csv,
        out_root=tmp_path / "repaired",
        anchor_mode="positive_only",
        generated_at_local="2026-05-05T00:00:00+09:00",
    )

    by_ligand = {row["ligand_id"]: row for row in rows}
    assert by_ligand["CHEMBL301265"]["allatom_force_anchor_applied"] is True
    assert by_ligand["decoy_basic"]["allatom_force_anchor_applied"] is False
    assert by_ligand["CHEMBL301265"]["target_cation_anchor_distance_A_mean"] != ""
    assert by_ligand["decoy_basic"]["target_cation_anchor_distance_A_mean"] == ""
