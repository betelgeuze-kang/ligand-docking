from __future__ import annotations

from pathlib import Path

from tools.build_selected_allatom_aligned_reference import build_aligned_reference
from tools.native_target_registry import canonicalize_target_name, find_matching_target_row


def _write_native_complex(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2       3.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  SER A   3       0.000   3.000   0.000  1.00 20.00           C",
                "HETATM    4  C1  LIG L   1       1.000   1.000   0.000  1.00 20.00           C",
                "HETATM    5  C2  LIG L   1       1.500   1.300   0.200  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_pose(path: Path, *, shift_x: float = 9.0, shift_y: float = 4.0) -> None:
    path.write_text(
        "\n".join(
            [
                f"HETATM    1  C1  LIG L   1      {shift_x:6.3f}  {shift_y:6.3f}   0.000  1.00 20.00           C",
                f"HETATM    2  C2  LIG L   1      {shift_x + 0.5:6.3f}  {shift_y + 0.3:6.3f}   0.200  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_viewer_reference(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1      10.000  10.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA A   2      13.000  10.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  SER A   3      10.000  13.000   0.000  1.00 20.00           C",
                "HETATM    4  C1  LIG L   1      11.000  11.000   0.000  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_aligned_reference_uses_native_ligand_centroid_translation(tmp_path: Path) -> None:
    native_path = tmp_path / "native_complex.pdb"
    pose_path = tmp_path / "pose.pdb"
    out_path = tmp_path / "aligned_reference.pdb"
    _write_native_complex(native_path)
    _write_pose(pose_path)

    payload = build_aligned_reference(
        native_structure_path=str(native_path),
        ligand_pose_pdb=str(pose_path),
        out_pdb=str(out_path),
    )

    assert payload["ready"] is True
    assert payload["alignment_mode"] == "native_ligand_centroid_translation"
    assert Path(payload["aligned_reference_pdb"]).exists()
    out_text = out_path.read_text(encoding="utf-8")
    assert "REMARK SELECTED_ALLATOM_ALIGNMENT_MODE native_ligand_centroid_translation" in out_text
    assert "HETATM" in out_text


def test_build_aligned_reference_uses_viewer_reference_kabsch_when_ca_context_is_available(tmp_path: Path) -> None:
    native_path = tmp_path / "native_complex.pdb"
    pose_path = tmp_path / "pose.pdb"
    viewer_path = tmp_path / "viewer_reference.pdb"
    out_path = tmp_path / "aligned_reference.pdb"
    _write_native_complex(native_path)
    _write_pose(pose_path)
    _write_viewer_reference(viewer_path)

    payload = build_aligned_reference(
        native_structure_path=str(native_path),
        ligand_pose_pdb=str(pose_path),
        viewer_reference_pdb=str(viewer_path),
        out_pdb=str(out_path),
    )

    assert payload["ready"] is True
    assert payload["alignment_mode"] == "viewer_reference_kabsch"
    assert payload["native_protein_ca_count"] == 3
    assert Path(payload["aligned_reference_pdb"]).exists()


def test_find_matching_target_row_handles_aliases() -> None:
    rows = [
        {
            "target": "SARS-CoV-2 Mpro",
            "native_pdb_path": "data/public_structures/selected_allatom_native_v1/sars_cov_2_mpro_pdb_6LU7.pdb",
            "pdb_id": "6LU7",
            "target_aliases": "sars_cov_2_mpro;SARS-CoV-2 3CLpro",
        }
    ]

    resolved = find_matching_target_row(rows, "sars_cov_2_mpro")

    assert canonicalize_target_name("COVID-19 Mpro") == "SARS-CoV-2 Mpro"
    assert resolved["pdb_id"] == "6LU7"
