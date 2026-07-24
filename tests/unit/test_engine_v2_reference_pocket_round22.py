from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.cli import run_canonical_docking
from betelgeuze_engine_v2.cli_dispatch import main as dispatch_main
from betelgeuze_engine_v2.molecular import write_canonical_system_json
from betelgeuze_engine_v2.reference_pocket import (
    REFERENCE_POCKET_DERIVATION_SCHEMA_ID,
    REFERENCE_POCKET_POLICY_ID,
    ReferencePocketError,
    derive_reference_pocket_document,
    derive_reference_pocket_from_canonical_bytes,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="reference-pocket-fixture",
        parser_version="1.0.0",
    )


def _ligand(*, include_far_hydrogen: bool = False) -> AllAtomSystem:
    elements = ["C", "N", "C", "O"]
    coordinates = [
        [0.0, 0.0, 0.0],
        [1.4, 0.0, 0.0],
        [2.8, 0.3, 0.0],
        [4.1, 1.0, 0.2],
    ]
    bonds = [
        Bond(index=0, atom_i=0, atom_j=1, order=1.0),
        Bond(index=1, atom_i=1, atom_j=2, order=1.0),
        Bond(index=2, atom_i=2, atom_j=3, order=1.0),
    ]
    if include_far_hydrogen:
        elements.append("H")
        coordinates.append([100.0, 100.0, 100.0])
        bonds.append(Bond(index=3, atom_i=0, atom_j=4, order=1.0))
    atomic_numbers = {"H": 1, "C": 6, "N": 7, "O": 8}
    atoms = tuple(
        Atom(
            index=index,
            name=f"L{index}",
            element=element,
            atomic_number=atomic_numbers[element],
            residue_index=0,
        )
        for index, element in enumerate(elements)
    )
    return AllAtomSystem(
        system_id="reference-pocket-ligand",
        atoms=atoms,
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("reference-pocket-ligand-source", "a" * 64),
    )


def _hydrogen_only_ligand() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="hydrogen-only",
        atoms=(
            Atom(
                index=0,
                name="H1",
                element="H",
                atomic_number=1,
                residue_index=0,
            ),
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="HYD",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0,),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("hydrogen-only-source", "f" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 4.0, 0.0],
        [4.0, 4.0, 0.0],
        [7.0, 0.0, 0.0],
        [60.0, 60.0, 60.0],
    )
    return AllAtomSystem(
        system_id="reference-pocket-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(len(coordinates))
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(coordinates))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("reference-pocket-receptor-source", "b" * 64),
    )


def test_reference_pocket_is_deterministic_and_receipt_bound() -> None:
    ligand = _ligand()
    first = derive_reference_pocket_document(
        ligand,
        ligand_artifact_sha256="c" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=3.0,
        minimum_radius_angstrom=5.0,
    )
    second = derive_reference_pocket_document(
        ligand,
        ligand_artifact_sha256="c" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=3.0,
        minimum_radius_angstrom=5.0,
    )
    assert _canonical_bytes(first) == _canonical_bytes(second)
    assert first["scope"] == "known_reference_pocket_redocking"
    metadata = first["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["schema_id"] == REFERENCE_POCKET_DERIVATION_SCHEMA_ID
    assert metadata["policy_id"] == REFERENCE_POCKET_POLICY_ID
    assert metadata["heavy_atom_indices"] == [0, 1, 2, 3]
    assert metadata["heavy_atom_count"] == 4
    assert metadata["hydrogen_coordinates_used"] is False
    assert metadata["receptor_coordinates_used"] is False
    assert metadata["pocket_prediction_performed"] is False
    assert metadata["claim_safe"] is False
    projection = dict(metadata)
    receipt = projection.pop("derivation_receipt_sha256")
    assert receipt == _sha256(projection)


def test_far_hydrogen_does_not_change_center_or_radius() -> None:
    base = derive_reference_pocket_document(
        _ligand(),
        ligand_artifact_sha256="c" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=2.0,
        minimum_radius_angstrom=1.0,
    )
    with_hydrogen = derive_reference_pocket_document(
        _ligand(include_far_hydrogen=True),
        ligand_artifact_sha256="d" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=2.0,
        minimum_radius_angstrom=1.0,
    )
    assert with_hydrogen["center_angstrom"] == base["center_angstrom"]
    assert with_hydrogen["radius_angstrom"] == base["radius_angstrom"]
    assert with_hydrogen["metadata"]["heavy_atom_indices"] == [0, 1, 2, 3]


def test_padding_changes_the_derived_radius_and_receipt() -> None:
    ligand = _ligand()
    first = derive_reference_pocket_document(
        ligand,
        ligand_artifact_sha256="c" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=1.0,
        minimum_radius_angstrom=1.0,
    )
    second = derive_reference_pocket_document(
        ligand,
        ligand_artifact_sha256="c" * 64,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=4.0,
        minimum_radius_angstrom=1.0,
    )
    assert second["radius_angstrom"] > first["radius_angstrom"]
    assert second["metadata"]["derivation_receipt_sha256"] != (
        first["metadata"]["derivation_receipt_sha256"]
    )


def test_hydrogen_only_reference_fails_closed() -> None:
    with pytest.raises(ReferencePocketError, match="no explicitly labelled heavy"):
        derive_reference_pocket_document(
            _hydrogen_only_ligand(),
            ligand_artifact_sha256="c" * 64,
            coordinate_frame_id="prepared-receptor-frame-v1",
        )


def test_reference_pocket_command_outputs_private_canonical_document(
    tmp_path: Path,
) -> None:
    ligand_path = tmp_path / "ligand.json"
    pocket_path = tmp_path / "pocket.json"
    write_canonical_system_json(_ligand(), ligand_path)
    status = dispatch_main(
        [
            "pocket-from-reference",
            "--ligand",
            str(ligand_path),
            "--coordinate-frame-id",
            "prepared-receptor-frame-v1",
            "--padding-angstrom",
            "3.0",
            "--minimum-radius-angstrom",
            "5.0",
            "--output",
            str(pocket_path),
        ]
    )
    assert status == 0
    assert stat.S_IMODE(os.stat(pocket_path).st_mode) == 0o600
    raw = pocket_path.read_bytes()
    assert raw.endswith(b"\n")
    document = json.loads(raw)
    assert document["scope"] == "known_reference_pocket_redocking"
    assert _canonical_bytes(document) + b"\n" == raw
    assert dispatch_main(
        [
            "pocket-from-reference",
            "--ligand",
            str(ligand_path),
            "--coordinate-frame-id",
            "prepared-receptor-frame-v1",
            "--output",
            str(pocket_path),
        ]
    ) == 2


def test_generated_pocket_is_accepted_by_canonical_docking(
    tmp_path: Path,
) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    pocket_path = tmp_path / "pocket.json"
    write_canonical_system_json(_receptor(), receptor_path)
    write_canonical_system_json(_ligand(), ligand_path)
    raw_ligand = ligand_path.read_bytes()
    pocket_document = derive_reference_pocket_from_canonical_bytes(
        raw_ligand,
        coordinate_frame_id="prepared-receptor-frame-v1",
        padding_angstrom=4.0,
        minimum_radius_angstrom=6.0,
    )
    pocket_path.write_bytes(_canonical_bytes(pocket_document) + b"\n")
    result = run_canonical_docking(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        candidate_count=3,
        top_k=2,
        max_torsions=1,
        translation_radius_angstrom=1.0,
        seed=181,
        receptor_margin_angstrom=4.0,
    )
    assert result["candidate_count"] == 3
    assert result["success_count"] + result["failure_count"] == 3
    assert result["pocket_artifact_sha256"] == hashlib.sha256(
        pocket_path.read_bytes()
    ).hexdigest()
    assert result["claim_safe"] is False
