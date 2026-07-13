from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest
import torch

from betelgeuze_engine_v2 import IndependentEngineV2
from betelgeuze_engine_v2.features import build_deterministic_atom_features
from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    MolecularPreparationError,
    SmilesParseError,
    attached_canonical_topology_sha256_matches,
    canonical_all_atom_systems_equal,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    molecular_preparation_blockers,
    parse_smiles,
    serialize_all_atom_system,
    validate_all_atom_system,
)
from betelgeuze_engine_v2.molecular import smiles as smiles_module


@pytest.fixture
def supported_local_rdkit(monkeypatch: pytest.MonkeyPatch) -> str:
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable in this test environment")
    version = rd_base.rdkitVersion
    monkeypatch.setattr(
        smiles_module, "_SUPPORTED_RDKIT_VERSIONS", frozenset({version})
    )
    return version


def test_production_allowlist_contains_only_repository_pin_and_current_local_version_fails_closed() -> (
    None
):
    assert smiles_module._SUPPORTED_RDKIT_VERSIONS == frozenset({"2025.9.6"})
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable in this test environment")
    if smiles_module._version_key(rd_base.rdkitVersion) != (2025, 9, 6):
        with pytest.raises(SmilesParseError) as exc_info:
            parse_smiles(b"C")
        assert exc_info.value.code == "unsupported_rdkit_version"
        assert exc_info.value.position is None


def test_unavailable_and_unallowlisted_rdkit_never_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> tuple[object, object]:
        raise ModuleNotFoundError("synthetic missing dependency")

    monkeypatch.setattr(smiles_module, "_import_rdkit", unavailable)
    with pytest.raises(SmilesParseError) as unavailable_error:
        parse_smiles(b"C")
    assert unavailable_error.value.code == "rdkit_unavailable"
    assert "synthetic" not in str(unavailable_error.value)

    def broken_binary() -> tuple[object, object]:
        raise RuntimeError("raw loader path and ABI detail")

    monkeypatch.setattr(smiles_module, "_import_rdkit", broken_binary)
    with pytest.raises(SmilesParseError) as broken_error:
        parse_smiles(b"C")
    assert broken_error.value.code == "rdkit_unavailable"
    assert "loader" not in str(broken_error.value)

    monkeypatch.undo()
    monkeypatch.setattr(smiles_module, "_SUPPORTED_RDKIT_VERSIONS", frozenset())
    with pytest.raises(SmilesParseError) as version_error:
        parse_smiles(b"C")
    assert version_error.value.code == "unsupported_rdkit_version"


@pytest.mark.parametrize(
    ("value", "source_id", "message"),
    [
        ("C", "", "data must be bytes"),
        (bytearray(b"C"), "", "data must be bytes"),
        (b"C", 7, "source_id must be a string"),
    ],
)
def test_public_api_uses_exact_bytes_and_string_types(
    value: object, source_id: object, message: str
) -> None:
    with pytest.raises(TypeError, match=message):
        parse_smiles(value, source_id=source_id)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("payload", "code", "position"),
    [
        (b"", "empty_input", 0),
        (b"C\xff", "non_ascii_input", 1),
        (b"C\nO", "multiline_input", 1),
        (b"C\rO", "multiline_input", 1),
        (b"C O", "whitespace_forbidden", 1),
        (b"C methane", "whitespace_forbidden", 1),
        (b"C |$C2;O1$|", "cxsmiles_forbidden", 2),
        (b"C\x00", "invalid_character", 1),
    ],
)
def test_lexical_failure_corpus_is_stable_and_precedes_rdkit(
    payload: bytes,
    code: str,
    position: int,
) -> None:
    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(payload)
    assert exc_info.value.code == code
    assert exc_info.value.position == position
    assert exc_info.value.detail
    decoded = payload.decode("ascii", errors="ignore")
    if len(decoded) >= 4:
        assert decoded not in str(exc_info.value)


def test_input_byte_cap_is_checked_before_adapter_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def should_not_load() -> tuple[object, object]:
        raise AssertionError("RDKit must not be loaded")

    monkeypatch.setattr(smiles_module, "_import_rdkit", should_not_load)
    payload = b"C" * (64 * 1024 + 1)
    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(payload)
    assert exc_info.value.code == "input_too_large"
    assert exc_info.value.position == 64 * 1024


@pytest.mark.parametrize("source_id", ["s" * 4_096, "é" * 2_048])
def test_source_id_utf8_boundary_is_bounded_without_parser_version_change(
    supported_local_rdkit: str,
    source_id: str,
) -> None:
    result = parse_smiles(b"C", source_id=source_id)

    assert smiles_module.SMILES_PARSER_VERSION == "1.4.0"
    assert result.system.provenance.source_id == source_id


@pytest.mark.parametrize(
    ("source_id", "code"),
    [
        ("s" * 4_097, "source_id_too_large"),
        ("é" * 2_049, "source_id_too_large"),
        ("\ud800", "invalid_source_id"),
    ],
)
def test_source_id_limit_and_unicode_scalar_validation_precede_rdkit(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    code: str,
) -> None:
    def should_not_load() -> tuple[object, object]:
        raise AssertionError("RDKit must not be loaded")

    monkeypatch.setattr(smiles_module, "_import_rdkit", should_not_load)
    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(b"C", source_id=source_id)

    assert exc_info.value.code == code
    assert exc_info.value.position is None
    assert source_id not in str(exc_info.value)


def test_methane_is_topology_only_with_manually_expanded_ordered_hydrogens(
    supported_local_rdkit: str,
) -> None:
    assert smiles_module.SMILES_PARSER_VERSION == "1.4.0"
    result = parse_smiles(b"C")
    assert "manual_bracket_and_implicit_hydrogen_expansion" in (
        result.system.provenance.operations
    )
    assert "manual_explicit_hydrogen_expansion" not in (
        result.system.provenance.operations
    )
    system = result.system
    assert system.coordinates.dtype == torch.float64
    assert tuple(system.coordinates.shape) == (0, 5, 3)
    assert [atom.element for atom in system.atoms] == ["C", "H", "H", "H", "H"]
    assert [
        atom.metadata.get("parent_source_atom_index") for atom in system.atoms[1:]
    ] == [0, 0, 0, 0]
    assert [atom.metadata.get("hydrogen_origin") for atom in system.atoms[1:]] == [
        "implicit"
    ] * 4
    assert system.atoms[0].metadata["formal_charge_source"] == (
        "smiles_source_via_pinned_rdkit"
    )
    assert [atom.metadata["formal_charge_source"] for atom in system.atoms[1:]] == [
        "manual_hydrogen_expansion_neutral"
    ] * 4
    assert [atom.metadata.get("hydrogen_ordinal") for atom in system.atoms[1:]] == [
        1,
        2,
        3,
        4,
    ]
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in system.bonds] == [
        (0, 1, 1.0),
        (0, 2, 1.0),
        (0, 3, 1.0),
        (0, 4, 1.0),
    ]
    assert result.coverage.source_atom_count == 1
    assert result.coverage.generated_hydrogen_count == 4
    assert result.coverage.all_hydrogens_explicit is True
    assert result.coverage.ingest_supported is True
    assert result.coverage.chemistry_supported is False
    assert result.coverage.parameterability_assessed is False
    assert validate_all_atom_system(system).valid
    topology_digest = canonical_topology_sha256(system)
    assert result.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert result.coverage.canonical_topology_sha256 == topology_digest
    assert system.provenance.metadata["canonical_topology_schema_id"] == (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    assert system.provenance.metadata["canonical_topology_sha256"] == topology_digest
    assert attached_canonical_topology_sha256_matches(system)


def test_generated_hydrogen_bond_validation_uses_constant_inventory_passes(
    supported_local_rdkit: str,
) -> None:
    class CountingBondTuple(tuple):
        iteration_count: int

        def __new__(cls, values):
            instance = super().__new__(cls, values)
            instance.iteration_count = 0
            return instance

        def __iter__(self):
            self.iteration_count += 1
            return super().__iter__()

    iteration_counts: list[int] = []
    for source in (b"C", b"CCCC"):
        system = parse_smiles(source).system
        bonds = CountingBondTuple(system.bonds)
        smiles_module._revalidate_canonical_graph(
            system.atoms,
            bonds,
            expected_formal_charge_total=0,
        )
        iteration_counts.append(bonds.iteration_count)

    assert iteration_counts[0] == iteration_counts[1]


def test_source_explicit_hydrogens_and_positive_maps_preserve_source_atom_order(
    supported_local_rdkit: str,
) -> None:
    result = parse_smiles(b"[H:2]O[H:3]")
    assert [
        (atom.index, atom.element, atom.atom_map) for atom in result.system.atoms
    ] == [
        (0, "H", 2),
        (1, "O", None),
        (2, "H", 3),
    ]
    assert [atom.metadata["source_atom_index"] for atom in result.system.atoms] == [
        0,
        1,
        2,
    ]
    assert result.coverage.generated_hydrogen_count == 0
    assert result.coverage.atom_map_count == 2


def test_aromatic_graph_and_blocker_are_preserved(supported_local_rdkit: str) -> None:
    result = parse_smiles(b"c1ccccc1")
    assert result.coverage.source_atom_count == 6
    assert result.coverage.expanded_atom_count == 12
    assert result.coverage.aromatic_atom_count == 6
    assert sum(bond.aromatic and bond.order == 1.5 for bond in result.system.bonds) == 6
    assert "aromaticity_not_independently_verified" in result.coverage.blockers

    first_aromatic = next(bond for bond in result.system.bonds if bond.aromatic)
    tampered_bonds = tuple(
        replace(bond, order=1.0, aromatic=False)
        if bond.index == first_aromatic.index
        else bond
        for bond in result.system.bonds
    )
    with pytest.raises(SmilesParseError, match="aromatic bond is not part"):
        smiles_module._revalidate_canonical_graph(
            result.system.atoms,
            tampered_bonds,
            expected_formal_charge_total=0,
        )


def test_aromatic_component_bridge_is_rejected_even_when_edge_count_equals_vertex_count(
    supported_local_rdkit: str,
) -> None:
    system = parse_smiles(b"c1ccccc1").system
    terminal_index = system.metadata["source_atom_count"]
    atoms = list(system.atoms)
    atoms[terminal_index] = replace(
        atoms[terminal_index],
        element="C",
        atomic_number=6,
        aromatic=True,
        metadata={},
    )
    bonds = list(system.bonds)
    terminal_bond_index = next(
        bond.index for bond in bonds if terminal_index in (bond.atom_i, bond.atom_j)
    )
    bonds[terminal_bond_index] = replace(
        bonds[terminal_bond_index],
        order=1.5,
        aromatic=True,
    )

    with pytest.raises(SmilesParseError, match="aromatic bond is not part"):
        smiles_module._revalidate_canonical_graph(
            tuple(atoms),
            tuple(bonds),
            expected_formal_charge_total=0,
        )


def test_disconnected_charged_fragments_are_preserved_as_l1_l2_components(
    supported_local_rdkit: str,
) -> None:
    result = parse_smiles(b"[NH4+].[Cl-]")
    system = result.system
    assert result.coverage.fragment_count == 2
    assert result.coverage.formal_charge_total == 0
    assert [atom.formal_charge for atom in system.atoms[:2]] == [1, -1]
    assert [chain.chain_id for chain in system.chains] == ["L1", "L2"]
    assert [residue.name for residue in system.residues] == ["L1", "L2"]
    assert system.residues[0].atom_indices == (0, 2, 3, 4, 5)
    assert system.residues[1].atom_indices == (1,)
    assert [atom.metadata.get("hydrogen_origin") for atom in system.atoms[2:]] == [
        "bracket_explicit",
    ] * 4
    assert "disconnected_fragment_roles_not_assessed" in result.coverage.blockers


def test_isotopic_source_hydrogens_are_typed_and_not_regenerated(
    supported_local_rdkit: str,
) -> None:
    result = parse_smiles(b"[2H]O[3H]")
    assert [atom.isotope_mass_number for atom in result.system.atoms] == [2, None, 3]
    assert result.coverage.isotope_count == 2
    assert result.coverage.generated_hydrogen_count == 0


def test_mapped_chiral_atom_and_ez_bond_are_typed_but_independently_blocked(
    supported_local_rdkit: str,
) -> None:
    chiral = parse_smiles(b"[C@H:17](F)(Cl)Br")
    assert chiral.system.atoms[0].atom_map == 17
    assert chiral.system.atoms[0].stereo in {"R", "S"}
    assert chiral.coverage.typed_atom_stereo_count == 1
    assert "cip_assignment_not_independently_verified" in chiral.coverage.blockers
    assert "stereo_geometry_unavailable" in chiral.coverage.blockers
    opposite_chiral = parse_smiles(b"[C@@H:17](F)(Cl)Br")
    assert opposite_chiral.system.atoms[0].stereo in {"R", "S"}
    assert opposite_chiral.system.atoms[0].stereo != chiral.system.atoms[0].stereo
    assert (
        opposite_chiral.coverage.ordered_topology_sha256
        != chiral.coverage.ordered_topology_sha256
    )

    alkene = parse_smiles(b"F/C=C/F")
    double_bond = next(bond for bond in alkene.system.bonds if bond.order == 2.0)
    assert double_bond.stereo in {"E", "Z"}
    assert alkene.coverage.typed_bond_stereo_count == 1
    assert "cip_assignment_not_independently_verified" in alkene.coverage.blockers
    opposite_alkene = parse_smiles(b"F/C=C\\F")
    opposite_double = next(
        bond for bond in opposite_alkene.system.bonds if bond.order == 2.0
    )
    assert opposite_double.stereo in {"E", "Z"}
    assert opposite_double.stereo != double_bond.stereo
    assert (
        opposite_alkene.coverage.ordered_topology_sha256
        != alkene.coverage.ordered_topology_sha256
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"C(", "invalid_smiles"),
        (b"*", "wildcard_atom_forbidden"),
        (b"[CH3]", "radical_atom_forbidden"),
        (b"C~C", "query_bond_forbidden"),
        (b"N->[Cu]", "unsupported_bond"),
        (b"C:O", "inconsistent_aromatic_bond"),
        (b"[CH3:7][OH:7]", "duplicate_atom_map"),
        (b"[999CH4]", "unsupported_isotope"),
        (b"F[Pt@SP1](Cl)(Br)I", "unsupported_atom_stereo"),
        (b"[C@](F)(F)(Cl)Br", "stereo_marker_not_retained"),
        (b"[C@@](F)(F)(Cl)Br", "stereo_marker_not_retained"),
        (b"F/C=C(/F)F", "stereo_marker_not_retained"),
        (b"F/C=C(\\F)F", "stereo_marker_not_retained"),
    ],
)
def test_chemistry_failure_corpus_is_fail_closed(
    supported_local_rdkit: str,
    payload: bytes,
    code: str,
) -> None:
    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(payload)
    assert exc_info.value.code == code
    assert payload.decode("ascii") not in str(exc_info.value)


@pytest.mark.parametrize(
    ("limit_name", "limit_value", "payload", "code"),
    [
        ("_MAX_SOURCE_ATOMS", 0, b"C", "too_many_source_atoms"),
        ("_MAX_EXPANDED_ATOMS", 1, b"C", "too_many_expanded_atoms"),
        ("_MAX_BONDS", 0, b"CC", "too_many_bonds"),
        ("_MAX_FRAGMENTS", 1, b"C.C", "too_many_fragments"),
    ],
)
def test_fixed_graph_caps_fail_closed_without_large_allocations(
    supported_local_rdkit: str,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit_value: int,
    payload: bytes,
    code: str,
) -> None:
    monkeypatch.setattr(smiles_module, limit_name, limit_value)
    with pytest.raises(SmilesParseError) as exc_info:
        parse_smiles(payload)
    assert exc_info.value.code == code


def test_result_and_coverage_are_json_safe_deterministic_and_raw_text_free(
    supported_local_rdkit: str,
) -> None:
    raw = b"[13CH3:777][NH3+:778]"
    first = parse_smiles(raw, source_id="opaque-fixture")
    second = parse_smiles(raw, source_id="opaque-fixture")
    summary = json.dumps(first.to_dict(), sort_keys=True, allow_nan=False)
    snapshot = serialize_all_atom_system(first.system)

    assert first.system.provenance.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert (
        first.coverage.ordered_topology_sha256
        == second.coverage.ordered_topology_sha256
    )
    assert first.coverage.canonical_topology_sha256 == canonical_topology_sha256(
        first.system
    )
    assert first.coverage.canonical_topology_sha256 == (
        second.coverage.canonical_topology_sha256
    )
    assert first.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert first.coverage.ordered_topology_sha256 != (
        first.coverage.canonical_topology_sha256
    )
    assert first.system.provenance.metadata["ordered_topology_sha256"] == (
        first.coverage.ordered_topology_sha256
    )
    assert attached_canonical_topology_sha256_matches(first.system)
    assert snapshot == serialize_all_atom_system(second.system)
    assert raw.decode("ascii") not in summary
    assert raw.decode("ascii").encode("ascii") not in snapshot
    assert '"normalized_smiles":' not in summary
    assert '"isomeric_smiles":' not in summary
    normalized_hash = first.system.provenance.metadata[
        "normalized_isomeric_smiles_sha256"
    ]
    assert len(normalized_hash) == 64
    int(normalized_hash, 16)


def test_topology_only_snapshot_round_trip_and_execution_readiness_remain_closed(
    supported_local_rdkit: str,
) -> None:
    result = parse_smiles(b"CCO")
    system = result.system
    payload = serialize_all_atom_system(system)
    restored = deserialize_all_atom_system(payload)
    blockers = molecular_preparation_blockers(system)

    assert tuple(restored.coordinates.shape) == (0, len(restored.atoms), 3)
    assert canonical_all_atom_systems_equal(system, restored)
    assert (
        canonical_topology_sha256(restored) == result.coverage.canonical_topology_sha256
    )
    assert attached_canonical_topology_sha256_matches(restored)
    assert system.provenance.preparation_ready is False
    assert "coordinates_missing" in blockers
    assert "preparation_not_complete" in blockers
    assert set(result.coverage.blockers).issubset(blockers)
    with pytest.raises(MolecularPreparationError):
        build_deterministic_atom_features(system)
    with pytest.raises(MolecularPreparationError):
        IndependentEngineV2().run(system)
