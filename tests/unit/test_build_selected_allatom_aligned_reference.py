from __future__ import annotations

from pathlib import Path

from tools import build_selected_allatom_aligned_reference as mod


def _write_structure(path: Path, *, include_ligand: bool = True) -> None:
    lines = [
        "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
        "ATOM      2  CA  ALA A   2       4.000   0.000   0.000  1.00 20.00           C",
        "ATOM      3  CA  SER A   3       0.000   4.000   0.000  1.00 20.00           C",
    ]
    if include_ligand:
        lines.extend(
            [
                "HETATM    4  C1  LIG L   1       1.500   1.000   0.000  1.00 20.00           C",
                "HETATM    5  C2  LIG L   1       2.000   1.300   0.200  1.00 20.00           C",
            ]
        )
    lines.extend(["END", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_pose(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "HETATM    1  C1  LIG L   1       8.500   1.000   0.000  1.00 20.00           C",
                "HETATM    2  C2  LIG L   1       9.000   1.300   0.200  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_aligned_reference_uses_viewer_reference_kabsch(tmp_path: Path) -> None:
    native_path = tmp_path / "native.pdb"
    viewer_reference_path = tmp_path / "viewer_reference.pdb"
    pose_path = tmp_path / "pose.pdb"
    out_path = tmp_path / "aligned_reference.pdb"
    _write_structure(native_path, include_ligand=True)
    _write_structure(viewer_reference_path, include_ligand=True)
    _write_pose(pose_path)

    payload = mod.build_aligned_reference(
        native_structure_path=str(native_path),
        ligand_pose_pdb=str(pose_path),
        viewer_reference_pdb=str(viewer_reference_path),
        out_pdb=str(out_path),
    )

    assert payload["ready"] is True
    assert payload["alignment_mode"] == "viewer_reference_kabsch"
    assert payload["native_protein_ca_count"] == 3
    assert payload["pose_ligand_atom_count"] == 2
    assert payload["aligned_reference_pdb"] == str(out_path)
    rendered = out_path.read_text(encoding="utf-8")
    assert "REMARK SELECTED_ALLATOM_ALIGNMENT_MODE viewer_reference_kabsch" in rendered
    assert "HETATM" in rendered


def test_build_aligned_reference_translates_from_pocket_center_when_native_has_no_ligand(
    tmp_path: Path,
) -> None:
    native_path = tmp_path / "native_no_ligand.pdb"
    pose_path = tmp_path / "pose.pdb"
    out_path = tmp_path / "aligned_reference.pdb"
    _write_structure(native_path, include_ligand=False)
    _write_pose(pose_path)

    payload = mod.build_aligned_reference(
        native_structure_path=str(native_path),
        ligand_pose_pdb=str(pose_path),
        viewer_reference_pdb=str(tmp_path / "missing_viewer_reference.pdb"),
        out_pdb=str(out_path),
        pocket_center=(0.0, 0.0, 0.0),
    )

    assert payload["ready"] is True
    assert payload["alignment_mode"] == "pocket_center_translation"
    assert payload["native_anchor_atom_count"] == 0
    assert payload["aligned_reference_pdb"] == str(out_path)
    rendered = out_path.read_text(encoding="utf-8")
    assert "REMARK SELECTED_ALLATOM_ALIGNMENT_MODE pocket_center_translation" in rendered

