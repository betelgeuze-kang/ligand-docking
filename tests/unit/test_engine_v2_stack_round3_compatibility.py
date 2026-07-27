from __future__ import annotations

# Torch is optional for collection, so imports depending on it intentionally follow
# the importorskip guard below.
# ruff: noqa: E402

import json

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_system_sha256,
)
from betelgeuze_engine_v2.molecular import (
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
)


def _system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="round3-compat",
        atoms=(
            Atom(
                index=0,
                name="C1",
                element="C",
                atomic_number=6,
                residue_index=0,
                metadata={
                    "coordinate_binary64_bits_hex": [
                        "0000000000000000",
                        "0000000000000000",
                        "0000000000000000",
                    ]
                },
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
        coordinates=torch.tensor(
            [[[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
        provenance=StructureProvenance(
            source_format="unit",
            source_id="round3-compat-source",
            source_sha256="a" * 64,
            parser_name="round3-compat-parser",
            parser_version="1.0.0",
        ),
        metadata={"ordered_steps": ["ingest", "canonicalize"]},
    )


def test_frozen_metadata_remains_json_container_compatible() -> None:
    system = _system()
    assert isinstance(system.metadata, dict)
    assert isinstance(system.metadata["ordered_steps"], list)
    assert system.metadata["ordered_steps"] == ["ingest", "canonicalize"]
    assert system.atoms[0].metadata[
        "coordinate_binary64_bits_hex"
    ] == [
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
    ]
    assert json.loads(json.dumps(dict(system.metadata))) == {
        "ordered_steps": ["ingest", "canonicalize"]
    }
    with pytest.raises((AttributeError, TypeError)):
        system.metadata["ordered_steps"].append("mutate")
    with pytest.raises(TypeError):
        system.metadata["new"] = True
    with pytest.raises(TypeError):
        system.metadata.update({"new": True})


def test_json_text_input_is_normalized_but_byte_artifacts_remain_strict() -> None:
    system = _system()
    document = json.loads(canonical_system_json_bytes(system))
    standard_json_text = json.dumps(document)
    restored = all_atom_system_from_canonical_json(standard_json_text)
    assert canonical_system_sha256(restored) == canonical_system_sha256(system)

    noncanonical_bytes = standard_json_text.encode("ascii")
    with pytest.raises(Exception, match="not canonical"):
        all_atom_system_from_canonical_json(noncanonical_bytes)
