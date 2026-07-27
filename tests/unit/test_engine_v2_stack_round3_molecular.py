from __future__ import annotations

# Torch is optional for collection, so imports depending on it intentionally follow
# the importorskip guard below.
# ruff: noqa: E402

from dataclasses import replace
import os
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    STACK_ROUND3_MOLECULAR_SHA256,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    MolecularIntegrityError,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_system_sha256,
    chemical_graph_sha256,
    indexed_topology_sha256,
    source_bound_topology_sha256,
)
from betelgeuze_engine_v2.molecular import (
    CanonicalSerializationError,
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    write_canonical_system_json,
)


def _system(
    *,
    coordinates: torch.Tensor | None = None,
    provenance: StructureProvenance | None = None,
) -> AllAtomSystem:
    return AllAtomSystem(
        system_id="round3-system",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                metadata={"nested": {"labels": ["a", "b"]}},
            ),
            Atom(
                index=1,
                name="O1",
                element="O",
                atomic_number=8,
                residue_index=0,
            ),
        ),
        bonds=(Bond(index=0, atom_i=0, atom_j=1, order=1.0),),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=(
            torch.tensor(
                [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]]],
                dtype=torch.float64,
            )
            if coordinates is None
            else coordinates
        ),
        provenance=(
            StructureProvenance(
                source_format="unit",
                source_id="round3-source",
                source_sha256="a" * 64,
                parser_name="round3-parser",
                parser_version="1.0.0",
                metadata={"review": {"labels": ["fixture"]}},
            )
            if provenance is None
            else provenance
        ),
        cell=UnitCell.orthorhombic(
            (20.0, 20.0, 20.0),
            dtype=torch.float64,
            periodic=(False, False, False),
        ),
        metadata={"workflow": {"steps": ["ingest", "canonicalize"]}},
    )


def test_round3_receipt_and_caller_tensor_cloning() -> None:
    assert len(STACK_ROUND3_MOLECULAR_SHA256) == 64
    source = torch.tensor(
        [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]]],
        dtype=torch.float64,
    )
    system = _system(coordinates=source)
    expected = system.coordinates.clone()
    source.add_(100.0)
    assert torch.equal(system.coordinates, expected)
    assert len(system.integrity_sha256) == 64


def test_integrity_metadata_stays_outside_public_dataclass_state() -> None:
    system = _system()
    assert "_integrity_sha256" not in system.__dict__
    reconstructed = AllAtomSystem(
        **{
            **system.__dict__,
            "coordinates": torch.cat(
                (system.coordinates, system.coordinates),
                dim=0,
            ),
        }
    )
    assert reconstructed.model_count == 2
    assert len(reconstructed.integrity_sha256) == 64


def test_molecular_metadata_is_recursively_immutable() -> None:
    system = _system()
    with pytest.raises(TypeError):
        system.metadata["new"] = True
    with pytest.raises(TypeError):
        system.metadata["workflow"]["new"] = True
    with pytest.raises(AttributeError):
        system.metadata["workflow"]["steps"].append("mutate")
    with pytest.raises(TypeError):
        system.atoms[0].metadata["nested"]["new"] = True
    with pytest.raises(TypeError):
        system.provenance.metadata["review"]["new"] = True


def test_in_place_coordinate_or_cell_mutation_fails_closed() -> None:
    system = _system()
    system.coordinates.add_(1.0)
    with pytest.raises(MolecularIntegrityError, match="changed after construction"):
        canonical_system_sha256(system)

    other = _system()
    assert other.cell is not None
    other.cell.vectors.mul_(2.0)
    with pytest.raises(MolecularIntegrityError, match="changed after construction"):
        other.assert_integrity()


def test_strict_canonical_reader_rejects_duplicate_and_noncanonical_json() -> None:
    with pytest.raises(CanonicalSerializationError, match="invalid or ambiguous"):
        all_atom_system_from_canonical_json(
            b'{"schema_id":"x","schema_id":"x"}'
        )

    system = _system()
    canonical = canonical_system_json_bytes(system)
    noncanonical = b"{ " + canonical[1:]
    with pytest.raises(CanonicalSerializationError, match="not canonical"):
        all_atom_system_from_canonical_json(noncanonical)


def test_durable_canonical_writer_round_trips_with_private_mode(tmp_path) -> None:
    system = _system()
    output = tmp_path / "system.json"
    written = write_canonical_system_json(system, output)
    assert written == output
    assert stat.S_IMODE(os.stat(output).st_mode) == 0o600
    raw = output.read_bytes()
    assert raw.endswith(b"\n")
    reconstructed = all_atom_system_from_canonical_json(raw)
    assert canonical_system_sha256(reconstructed) == canonical_system_sha256(system)


def test_chemical_indexed_and_source_bound_identities_are_separate() -> None:
    system = _system()
    changed_source = replace(
        system.provenance,
        source_id="another-source",
        source_sha256="b" * 64,
    )
    same_structure_new_source = replace(system, provenance=changed_source)

    assert chemical_graph_sha256(same_structure_new_source) == chemical_graph_sha256(
        system
    )
    assert indexed_topology_sha256(
        same_structure_new_source
    ) == indexed_topology_sha256(system)
    assert source_bound_topology_sha256(
        same_structure_new_source
    ) != source_bound_topology_sha256(system)

    shifted = system.with_coordinates(
        system.coordinates + 2.0,
        operation="round3-shift",
    )
    assert chemical_graph_sha256(shifted) == chemical_graph_sha256(system)
    assert indexed_topology_sha256(shifted) == indexed_topology_sha256(system)
    assert source_bound_topology_sha256(shifted) == source_bound_topology_sha256(
        system
    )
    assert canonical_system_sha256(shifted) != canonical_system_sha256(system)
