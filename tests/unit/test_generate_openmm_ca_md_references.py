from __future__ import annotations

from pathlib import Path

from tools import generate_openmm_ca_md_references as mod


def test_native_pdb_path_for_target_prefers_registered_research_constant_path(
    monkeypatch, tmp_path: Path
) -> None:
    native = tmp_path / "custom_native.pdb"
    native.write_text(
        "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(
        mod.ResearchConstants.CHALLENGES,
        "Custom Native Target",
        {"n_res": 1, "native_pdb_path": str(native)},
    )

    assert mod._native_pdb_path_for_target("Custom Native Target") == str(native)


def test_load_ca_coords_from_pdb_can_filter_canonical_chain(tmp_path: Path) -> None:
    native = tmp_path / "multichain.pdb"
    native.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       1.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  GLY B   1       2.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  ALA B   2       3.000   0.000   0.000  1.00 20.00           C",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    coords = mod._load_ca_coords_from_pdb(str(native), chain_id="B")

    assert coords.shape == (2, 3)
    assert coords[:, 0].tolist() == [2.0, 3.0]
