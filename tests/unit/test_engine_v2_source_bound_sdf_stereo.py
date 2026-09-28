from __future__ import annotations

from dataclasses import replace

import pytest


pytest.importorskip("torch")
pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402

from betelgeuze_engine_v2.docking import conformers  # noqa: E402
from betelgeuze_engine_v2.io import parse_sdf_v2000  # noqa: E402


def _directed_sdf(stereo_code: int = 1) -> bytes:
    atoms = (
        ("F", (1.0, 1.0, 1.0)),
        ("C", (0.0, 0.0, 0.0)),
        ("Cl", (-1.0, -1.0, 1.0)),
        ("Br", (-1.0, 1.0, -1.0)),
        ("H", (1.0, -1.0, -1.0)),
    )
    lines = [
        "synthetic reversed wedge",
        "EngineV2",
        "source orientation fixture",
        f"{5:3d}{4:3d}  0  0  0  0            999 V2000",
    ]
    for element, (x, y, z) in atoms:
        lines.append(
            f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}{0:2d}{0:3d}"
            "  0  0  0  0  0  0  0  0  0  0  0  0"
        )
    lines.append(f"{2:3d}{1:3d}{1:3d}{stereo_code:3d}  0  0  0")
    lines.extend(f"{2:3d}{index:3d}{1:3d}{0:3d}  0  0  0" for index in (3, 4, 5))
    return "\n".join([*lines, "M  END", "$$$$", ""]).encode("ascii")


def _text_projection(source_bytes: bytes) -> dict:
    projection = conformers._require_supported_source_molfile_fields(
        source_bytes.decode("ascii")
    )
    projection["rdkit_declared_valence_checks"] = []
    return projection


@pytest.mark.parametrize("stereo_code", (1, 4, 6))
@pytest.mark.parametrize("changed_side", ("metadata", "text"))
def test_source_text_projection_rejects_swapped_wedge_anchor(
    stereo_code: int, changed_side: str,
) -> None:
    source_bytes = _directed_sdf(stereo_code)
    source = parse_sdf_v2000(source_bytes)
    projection = _text_projection(source_bytes)
    conformers._require_source_text_projection_contract(projection, source)

    if changed_side == "metadata":
        source = replace(
            source,
            bonds=(
                replace(
                    source.bonds[0],
                    metadata={"sdf_v2000_stereo_first_atom_index": 0},
                ),
                *source.bonds[1:],
            ),
        )
    else:
        row = projection["bonds"][0]
        row["begin_atom_index"], row["end_atom_index"] = (
            row["end_atom_index"], row["begin_atom_index"],
        )

    with pytest.raises(
        conformers.ConformerPreparationError,
        match="source SDF bond projection is cross-wired",
    ):
        conformers._require_source_text_projection_contract(projection, source)


@pytest.mark.parametrize("anchor", (None, True, 1.0, "1", 4))
def test_source_contract_rejects_missing_or_invalid_wedge_anchor(anchor) -> None:
    source_bytes = _directed_sdf()
    source = parse_sdf_v2000(source_bytes)
    source = replace(
        source,
        bonds=(
            replace(
                source.bonds[0],
                metadata=({"sdf_v2000_stereo_first_atom_index": anchor}
                          if anchor is not None else {}),
            ),
            *source.bonds[1:],
        ),
    )
    with pytest.raises(
        conformers.ConformerPreparationError,
        match="source SDF wedge first-atom orientation is invalid",
    ):
        conformers._source_bond_projection(source)
    with pytest.raises(
        conformers.ConformerPreparationError,
        match="source SDF wedge first-atom orientation is invalid",
    ):
        conformers._require_source_text_projection_contract(
            _text_projection(source_bytes), source,
        )


def test_source_bound_parser_rejects_anchor_crosswired_to_authenticated_bytes() -> None:
    source_bytes = _directed_sdf()
    source = parse_sdf_v2000(source_bytes)
    conformers._source_bound_rdkit_molecule(source, source_bytes, chemistry=Chem)
    altered = replace(
        source,
        bonds=(
            replace(
                source.bonds[0],
                metadata={"sdf_v2000_stereo_first_atom_index": 0},
            ),
            *source.bonds[1:],
        ),
    )
    with pytest.raises(
        conformers.ConformerPreparationError,
        match="source system atom order, bond table, or coordinates do not match",
    ):
        conformers._source_bound_rdkit_molecule(altered, source_bytes, chemistry=Chem)


def test_nonstereo_source_bond_projection_preserves_existing_identity() -> None:
    source = parse_sdf_v2000(_directed_sdf(0))
    assert conformers._source_bond_projection(source) == tuple(
        (bond.index, bond.atom_i, bond.atom_j, bond.order, bond.aromatic, bond.stereo)
        for bond in source.bonds
    )
