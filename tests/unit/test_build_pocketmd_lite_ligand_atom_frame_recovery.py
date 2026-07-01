from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from tools.product import build_pocketmd_lite_ligand_atom_frame_recovery as mod


_INPUT_COLUMNS = [
    "entry_id",
    "target",
    "ligand_id",
    "required_collection_metrics",
    "selected_trajectory_npz",
    "selected_trajectory_source",
    "selected_trajectory_readable",
    "selected_trajectory_claim_grade_metric_fields_present",
    "protein_structure_source_path",
    "protein_structure_source_path_available",
    "ligand_smiles",
    "ligand_smiles_present",
    "collection_input_ready",
    "claim_grade_metrics_already_present",
]


def _write_input_csv(
    path: Path,
    npz_path: Path,
    *,
    smiles: str = "CCO",
    protein_path: str = "protein.pdb",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "entry_id": "ADRB2_GPCR_BLIND:ethanol",
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "ethanol",
                "required_collection_metrics": (
                    "local_min_ligand_rmsd_a;hbond_persistence;initial_clash_count"
                ),
                "selected_trajectory_npz": str(npz_path),
                "selected_trajectory_source": "unit_fixture",
                "selected_trajectory_readable": "true",
                "selected_trajectory_claim_grade_metric_fields_present": "false",
                "protein_structure_source_path": protein_path,
                "protein_structure_source_path_available": "true",
                "ligand_smiles": smiles,
                "ligand_smiles_present": "true",
                "collection_input_ready": "true",
                "claim_grade_metrics_already_present": "false",
            }
        )


def _write_npz(path: Path, *, protein_atom_frames: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "protein_ca": np.asarray([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]], dtype=np.float32),
        "ligand_frames": np.asarray(
            [
                [[2.8, 0.0, 0.0], [4.4, 0.0, 0.0]],
                [[3.0, 0.1, 0.0], [4.6, 0.1, 0.0]],
            ],
            dtype=np.float32,
        ),
        "frame_indices": np.asarray([0, 1], dtype=np.int32),
    }
    if protein_atom_frames:
        payload["protein_atom_frames"] = np.asarray(
            [
                [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [8.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [8.0, 0.0, 0.0]],
            ],
            dtype=np.float32,
        )
    np.savez(path, **payload)


def _write_protein_pdb(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00           N",
                "ATOM      2  CA  ALA A   1       1.500   0.000   0.000  1.00 20.00           C",
                "ATOM      3  C   ALA A   1       2.500   1.000   0.000  1.00 20.00           C",
                "ATOM      4  O   ALA A   1       3.500   1.000   0.000  1.00 20.00           O",
                "ATOM      5  H   ALA A   1      -0.500   0.000   0.000  1.00 20.00           H",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_recovery_writes_ligand_atom_frames_for_collection_ready_source(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    selected = tmp_path / "selected" / "ADRB2_GPCR_BLIND__rep0000__ethanol.npz"
    input_csv = tmp_path / "input.csv"
    out_root = tmp_path / "recovered"
    _write_npz(selected, protein_atom_frames=True)
    _write_input_csv(input_csv, selected)

    payload = mod.build_pocketmd_lite_ligand_atom_frame_recovery(
        input_csv=input_csv,
        out_root=out_root,
        search_roots=[],
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "pocketmd_lite_ligand_atom_frame_recovery_ready"
    assert summary["ligand_atom_frame_generated_count"] == 1
    assert summary["collection_input_candidate_ready_count"] == 1
    assert row["collection_input_candidate_ready"] is True
    assert row["ligand_atom_count"] == 3
    out_npz = Path(row["out_npz"])
    if not out_npz.is_absolute():
        out_npz = mod.ROOT / out_npz
    with np.load(out_npz, allow_pickle=False) as recovered:
        assert recovered["ligand_atom_frames"].shape == (2, 3, 3)
        assert recovered["protein_atom_frames"].shape == (2, 3, 3)
        assert recovered["ligand_atom_frame_claim_grade_metric_evidence"].item() is False
        assert str(recovered["ligand_atom_frame_source"].item()) == mod.FRAME_SOURCE


def test_recovery_keeps_ligand_only_rows_blocked_until_protein_atom_frames(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    selected = tmp_path / "selected" / "ADRB2_GPCR_BLIND__rep0000__ethanol.npz"
    input_csv = tmp_path / "input.csv"
    _write_npz(selected, protein_atom_frames=False)
    _write_input_csv(input_csv, selected)

    payload = mod.build_pocketmd_lite_ligand_atom_frame_recovery(
        input_csv=input_csv,
        out_root=tmp_path / "recovered",
        search_roots=[],
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "pocketmd_lite_ligand_atom_frame_recovery_partial_ready"
    assert summary["ligand_atom_frame_generated_count"] == 1
    assert summary["collection_input_candidate_ready_count"] == 0
    assert row["collection_input_candidate_ready"] is False
    assert "protein_atom_frames_missing" in row["blockers"]
    assert "protein_structure_source_path_unavailable" in row["blockers"]
    assert row["recommended_next_local_action"] == (
        "recover_or_generate_protein_atom_frames_then_run_claim_grade_metric_collector"
    )


def test_recovery_backfills_static_protein_atom_frames_from_pdb(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    selected = tmp_path / "selected" / "ADRB2_GPCR_BLIND__rep0000__ethanol.npz"
    protein_pdb = tmp_path / "protein.pdb"
    input_csv = tmp_path / "input.csv"
    out_root = tmp_path / "recovered"
    _write_npz(selected, protein_atom_frames=False)
    _write_protein_pdb(protein_pdb)
    _write_input_csv(input_csv, selected, protein_path=str(protein_pdb))

    payload = mod.build_pocketmd_lite_ligand_atom_frame_recovery(
        input_csv=input_csv,
        out_root=out_root,
        search_roots=[],
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "pocketmd_lite_ligand_atom_frame_recovery_ready"
    assert summary["collection_input_candidate_ready_count"] == 1
    assert summary["protein_atom_frame_missing_count"] == 0
    assert row["collection_input_candidate_ready"] is True
    assert row["protein_atom_frame_count"] == 4
    assert row["protein_atom_frame_source"] == mod.PROTEIN_FRAME_SOURCE
    assert row["blockers"] == []
    out_npz = Path(row["out_npz"])
    if not out_npz.is_absolute():
        out_npz = mod.ROOT / out_npz
    with np.load(out_npz, allow_pickle=False) as recovered:
        assert recovered["protein_atom_frames"].shape == (2, 4, 3)
        assert recovered["protein_atom_atomic_numbers"].tolist() == [7, 6, 6, 8]
        assert str(recovered["protein_atom_frame_source"].item()) == mod.PROTEIN_FRAME_SOURCE
        assert recovered["protein_atom_frame_claim_grade_metric_evidence"].item() is False


def test_main_writes_recovery_artifacts(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    selected = tmp_path / "selected" / "ADRB2_GPCR_BLIND__rep0000__ethanol.npz"
    input_csv = tmp_path / "input.csv"
    out_root = tmp_path / "recovered"
    out_json = tmp_path / "recovery.json"
    out_md = tmp_path / "recovery.md"
    out_csv = tmp_path / "recovery.csv"
    _write_npz(selected, protein_atom_frames=True)
    _write_input_csv(input_csv, selected)

    rc = mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--out-root",
            str(out_root),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "pocketmd_lite_ligand_atom_frame_recovery"
    assert out_md.read_text(encoding="utf-8").startswith(
        "# PocketMD Lite Ligand Atom Frame Recovery"
    )
    rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    assert rows[0]["entry_id"] == "ADRB2_GPCR_BLIND:ethanol"
