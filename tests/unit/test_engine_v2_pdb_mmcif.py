from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    MMCIF_PARSER_VERSION,
    PDB_PARSER_VERSION,
    STRUCTURE_INGEST_SUPPORT_SCOPE,
    StructureParseError,
    analyze_molecular_preparation,
    attached_canonical_topology_sha256_matches,
    attached_parser_observation_sha256_matches,
    canonical_all_atom_snapshot_digest,
    canonical_all_atom_systems_equal,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    parse_mmcif,
    parse_pdb,
    serialize_all_atom_system,
    validate_all_atom_system,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"


def _pdb_atom(
    record: str,
    serial: int,
    name: str,
    residue: str,
    chain: str,
    residue_number: int,
    x: float,
    y: float,
    z: float,
    element: str,
    *,
    altloc: str = " ",
    insertion_code: str = " ",
    occupancy: float = 1.0,
    b_factor: float = 20.0,
    segment_id: str = "",
    charge: str = "",
) -> str:
    return (
        f"{record:<6}{serial:5d} {name:<4}{altloc:1}{residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}   {x:8.3f}{y:8.3f}{z:8.3f}"
        f"{occupancy:6.2f}{b_factor:6.2f}{'':6}{segment_id:<4}{element:>2}{charge:>2}"
    )


def _cryst1(
    a: float = 20.0,
    b: float = 21.0,
    c: float = 22.0,
    alpha: float = 90.0,
    beta: float = 90.0,
    gamma: float = 90.0,
) -> str:
    return (
        f"CRYST1{a:9.3f}{b:9.3f}{c:9.3f}{alpha:7.2f}{beta:7.2f}{gamma:7.2f} "
        f"{'P 1':<11}{1:4d}"
    )


def _pdb(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_parse_existing_pdb_fixture_and_canonical_round_trip() -> None:
    source = (FIXTURES / "mini_protein.pdb").read_bytes()
    result = parse_pdb(source, source_id="tier-beta-mini-protein")
    system = result.system

    assert PDB_PARSER_VERSION == "1.8.0"
    assert system.system_id == "tier-beta-mini-protein"
    assert system.atom_count == 10
    assert system.model_count == 1
    assert len(system.residues) == 10
    assert len(system.chains) == 1
    assert system.chains[0].chain_id == "A"
    assert [atom.element for atom in system.atoms] == ["C"] * 10
    assert system.provenance.source_sha256 == hashlib.sha256(source).hexdigest()
    assert system.provenance.claim_safe is False
    assert result.coverage.bond_count == 0
    assert result.coverage.source_atom_row_count == 10
    assert result.coverage.altloc_status == "not_present"
    assert result.coverage.altloc_kept_row_count == 10
    assert result.coverage.altloc_discarded_row_count == 0
    assert result.coverage.support_scope == STRUCTURE_INGEST_SUPPORT_SCOPE
    assert result.coverage.syntax_ingest_supported is True
    assert result.coverage.to_dict()["support_scope"] == (
        STRUCTURE_INGEST_SUPPORT_SCOPE
    )
    assert "bond_topology_incomplete_or_unverified" in result.coverage.blockers
    assert validate_all_atom_system(system).valid
    topology_digest = canonical_topology_sha256(system)
    assert result.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert result.coverage.canonical_topology_sha256 == topology_digest
    assert system.provenance.metadata["canonical_topology_schema_id"] == (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    assert system.provenance.metadata["canonical_topology_sha256"] == topology_digest
    assert attached_canonical_topology_sha256_matches(system)
    repeated = parse_pdb(source, source_id="tier-beta-mini-protein")
    assert repeated.coverage.canonical_topology_sha256 == topology_digest

    payload = serialize_all_atom_system(system)
    restored = deserialize_all_atom_system(payload)
    assert canonical_all_atom_systems_equal(system, restored)
    assert canonical_all_atom_snapshot_digest(system) == canonical_all_atom_snapshot_digest(restored)
    assert canonical_topology_sha256(restored) == topology_digest
    assert attached_canonical_topology_sha256_matches(restored)


def test_pdb_explicit_altloc_selection_keeps_blank_and_requested_rows() -> None:
    source = _pdb(
        _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0.0, 0.0, 0.0, "N"),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 3, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "END",
    )
    result = parse_pdb(source, altloc_id="A")
    system = result.system

    assert [(atom.name, atom.altloc, atom.serial) for atom in system.atoms] == [
        ("N", "", 1),
        ("CA", "A", 2),
    ]
    assert torch.allclose(
        system.coordinates[0, :, 0],
        torch.tensor([0.0, 1.0], dtype=torch.float64),
    )
    assert result.coverage.source_atom_row_count == 3
    assert result.coverage.altloc_status == "explicit_id_selected"
    assert result.coverage.requested_altloc_id == "A"
    assert result.coverage.altloc_affected_residue_count == 1
    assert result.coverage.altloc_kept_row_count == 2
    assert result.coverage.altloc_discarded_row_count == 1
    assert "alternate_location_selection_not_supported" not in result.coverage.blockers
    assert "select_explicit_altloc_id/v1" in system.provenance.operations
    assert attached_canonical_topology_sha256_matches(system)
    ledger = system.metadata["pdb"]["altloc_selection"]
    assert ledger["models"][0]["kept_source_atom_ids"] == [1, 2]
    assert ledger["models"][0]["discarded_source_atom_ids"] == [3]


@pytest.mark.parametrize(
    ("altloc_id", "code"),
    [
        ("C", "requested_altloc_missing_for_residue"),
        ("", "invalid_altloc_id"),
        ("AA", "invalid_altloc_id"),
        (" ", "invalid_altloc_id"),
    ],
)
def test_pdb_explicit_altloc_selection_failures_are_stable(
    altloc_id: str,
    code: str,
) -> None:
    source = _pdb(
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "END",
    )
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(source, altloc_id=altloc_id)
    assert exc_info.value.code == code


def test_pdb_altloc_candidates_must_have_equal_atom_identity_and_no_blank_collision() -> None:
    unequal = _pdb(
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CB", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "END",
    )
    with pytest.raises(StructureParseError) as unequal_error:
        parse_pdb(unequal, altloc_id="A")
    assert unequal_error.value.code == "inconsistent_altloc_atom_identity"

    collision = _pdb(
        _pdb_atom("ATOM", 1, "CA", "GLY", "A", 1, 0.0, 0.0, 0.0, "C"),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        "END",
    )
    with pytest.raises(StructureParseError) as collision_error:
        parse_pdb(collision, altloc_id="A")
    assert collision_error.value.code == "altloc_blank_collision"

    tab_altloc = list(
        _pdb_atom("ATOM", 1, "CA", "GLY", "A", 1, 0.0, 0.0, 0.0, "C")
    )
    tab_altloc[16] = "\t"
    with pytest.raises(StructureParseError) as tab_error:
        parse_pdb(_pdb("".join(tab_altloc), "END"))
    assert tab_error.value.code == "invalid_text"


def test_pdb_altloc_selection_is_fixed_across_models_and_conect_fails_closed() -> None:
    mismatched_models = _pdb(
        "MODEL        1",
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "ENDMDL",
        "MODEL        2",
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.1, 0.0, 0.0, "C", altloc="A"
        ),
        "ENDMDL",
        "END",
    )
    with pytest.raises(StructureParseError) as model_error:
        parse_pdb(mismatched_models, altloc_id="A")
    assert model_error.value.code == "model_altloc_inventory_mismatch"

    conect = _pdb(
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        _pdb_atom("ATOM", 3, "N", "GLY", "A", 1, 0.0, 0.0, 0.0, "N"),
        "CONECT    1    3",
        "END",
    )
    with pytest.raises(StructureParseError) as conect_error:
        parse_pdb(conect, altloc_id="A")
    assert conect_error.value.code == "altloc_conect_not_supported"


def test_pdb_altloc_selection_aligns_models_and_remaps_ter_audit_position() -> None:
    multi_model = _pdb(
        "MODEL        1",
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "ENDMDL",
        "MODEL        2",
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.1, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.1, 0.0, 0.0, "C", altloc="B"
        ),
        "ENDMDL",
        "END",
    )
    selected = parse_pdb(multi_model, altloc_id="B")
    assert selected.system.coordinates.shape == (2, 1, 3)
    assert selected.system.atoms[0].altloc == "B"
    assert torch.allclose(
        selected.system.coordinates[:, 0, 0],
        torch.tensor([2.0, 2.1], dtype=torch.float64),
    )
    assert selected.coverage.source_atom_row_count == 4
    assert selected.coverage.altloc_kept_row_count == 2
    assert selected.coverage.altloc_discarded_row_count == 2

    with_ter = _pdb(
        _pdb_atom(
            "ATOM", 1, "CA", "GLY", "A", 1, 1.0, 0.0, 0.0, "C", altloc="A"
        ),
        _pdb_atom(
            "ATOM", 2, "CA", "GLY", "A", 1, 2.0, 0.0, 0.0, "C", altloc="B"
        ),
        "TER       3      GLY A   1 ",
        "END",
    )
    ter_selected = parse_pdb(with_ter, altloc_id="A")
    ter_record = ter_selected.system.metadata["pdb"]["ter_records_by_model"][0][
        "records"
    ][0]
    assert ter_record["after_atom_index"] == 0
    assert ter_record["after_atom_serial"] == 1


def test_parse_pdb_multimodel_cryst1_without_untyped_connectivity() -> None:
    source = _pdb(
        _cryst1(),
        "MODEL        1",
        _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0.0, 0.0, 0.0, "N"),
        _pdb_atom("ATOM", 2, "CA", "GLY", "A", 1, 1.4, 0.0, 0.0, "C"),
        "ENDMDL",
        "MODEL        2",
        _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0.1, 0.0, 0.0, "N"),
        _pdb_atom("ATOM", 2, "CA", "GLY", "A", 1, 1.5, 0.0, 0.0, "C"),
        "ENDMDL",
        "END",
    )
    result = parse_pdb(source)
    system = result.system
    assert system.coordinates.shape == (2, 2, 3)
    assert torch.allclose(system.coordinates[:, 0, 0], torch.tensor([0.0, 0.1], dtype=torch.float64))
    assert system.bonds == ()
    assert system.cell is not None
    assert system.cell.periodic == (False, False, False)
    assert torch.allclose(system.cell.orthorhombic_lengths(), torch.tensor([20.0, 21.0, 22.0], dtype=torch.float64))
    assert result.coverage.model_count == 2
    assert result.coverage.cell_present is True
    assert "crystallographic_cell_not_simulation_box" in result.coverage.blockers


def test_parse_pdb_preserves_insertion_hetero_segment_and_formal_charge() -> None:
    source = _pdb(
        _pdb_atom(
            "HETATM",
            7,
            "ZN",
            "ZN",
            "B",
            12,
            1.0,
            2.0,
            3.0,
            "Zn",
            insertion_code="A",
            segment_id="ION",
            charge="2+",
        ),
        "END",
    )
    result = parse_pdb(source)
    atom = result.system.atoms[0]
    residue = result.system.residues[0]
    assert atom.element == "Zn"
    assert atom.formal_charge == 2
    assert atom.metadata["formal_charge_source"] == "pdb_columns_79_80"
    assert atom.metadata["hydrogen_origin"] == "not_hydrogen"
    assert atom.metadata["pdb_segment_id"] == "ION"
    assert residue.insertion_code == "A"
    assert residue.hetero is True
    assert residue.entity_type == "unknown"
    assert result.coverage.hetero_residue_count == 1


def test_pdb_explicit_hydrogen_is_source_observed_not_completion() -> None:
    result = parse_pdb(
        _pdb(
            _pdb_atom(
                "ATOM",
                1,
                "H",
                "GLY",
                "A",
                1,
                0.0,
                0.0,
                0.0,
                "H",
            ),
            "END",
        )
    )
    atom = result.system.atoms[0]
    assert atom.metadata["hydrogen_origin"] == "source"
    assert atom.formal_charge_known is False
    assert atom.metadata["formal_charge_source"] == "missing_in_pdb"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff\xfe", "invalid_ascii"),
        (b"\x0b\x0c\x1c", "invalid_text"),
        (_pdb("HEADER unsupported", "END"), "unsupported_record"),
        (_pdb(_pdb_atom("ATOM", 1, "CA", "ALA", "A", 1, 0, 0, 0, "C", altloc="A"), "END"), "unsupported_altloc"),
        (_pdb(_pdb_atom("ATOM", 1, "CA", "ALA", "A", 1, 0, 0, 0, "C")[:76] + "  ", "END"), "missing_element"),
        (_pdb(_pdb_atom("ATOM", 1, "CA", "ALA", "A", 1, 0, 0, 0, "C")[:30] + "  1_0.0" + _pdb_atom("ATOM", 1, "CA", "ALA", "A", 1, 0, 0, 0, "C")[38:], "END"), "invalid_atom_coordinate"),
        (
            _pdb(
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                _pdb_atom("ATOM", 1, "CA", "GLY", "A", 1, 1, 0, 0, "C"),
                "END",
            ),
            "duplicate_atom_serial",
        ),
        (_pdb("MODEL        1", _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N")), "missing_endmdl"),
        (_pdb("MODEL        1", "ENDMDL", "END"), "empty_model"),
        (
            _pdb(
                "MODEL        1",
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                "ENDMDL",
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                "END",
            ),
            "atom_outside_model",
        ),
        (
            _pdb(
                "MODEL        1",
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                "ENDMDL",
                "MODEL        2",
                _pdb_atom("ATOM", 1, "CA", "GLY", "A", 1, 0, 0, 0, "C"),
                "ENDMDL",
                "END",
            ),
            "model_atom_identity_mismatch",
        ),
        (
            _pdb(
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                "CONECT    1    9",
                "END",
            ),
            "conect_atom_out_of_range",
        ),
        (
            _pdb(
                _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"),
                "TER       2      GLY A   1 ",
                _pdb_atom("ATOM", 2, "CA", "GLY", "A", 2, 1, 0, 0, "C"),
                "END",
            ),
            "chain_reopened_after_ter",
        ),
        (_pdb(_cryst1(a=0.0), _pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"), "END"), "invalid_cryst1"),
        (_pdb(_pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N"), "END", "ATOM"), "content_after_end"),
    ],
)
def test_pdb_failure_corpus(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(payload)
    assert exc_info.value.source_format == "pdb"
    assert exc_info.value.code == code


MMCIF_HEADERS = (
    "_atom_site.group_PDB",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_seq_id",
    "_atom_site.Cartn_x",
    "_atom_site.Cartn_y",
    "_atom_site.Cartn_z",
    "_atom_site.pdbx_PDB_model_num",
)


def _mmcif(rows: tuple[str, ...], *, headers: tuple[str, ...] = MMCIF_HEADERS, data_name: str = "fixture") -> bytes:
    lines = [f"data_{data_name}", "#", "loop_", *headers, *rows, "#"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_parse_existing_mmcif_fixture_and_canonical_round_trip() -> None:
    source = (FIXTURES / "mini_protein.cif").read_bytes()
    result = parse_mmcif(source)
    system = result.system

    assert MMCIF_PARSER_VERSION == "1.9.0"
    assert system.system_id == "tier_beta_mini_protein"
    assert system.atom_count == 10
    assert len(system.residues) == 10
    assert len(system.chains) == 1
    assert system.model_count == 1
    assert system.provenance.source_sha256 == hashlib.sha256(source).hexdigest()
    assert result.coverage.bond_count == 0
    assert result.coverage.source_atom_row_count == 10
    assert result.coverage.altloc_status == "not_present"
    assert result.coverage.altloc_kept_row_count == 10
    assert result.coverage.altloc_discarded_row_count == 0
    assert result.coverage.support_scope == STRUCTURE_INGEST_SUPPORT_SCOPE
    assert result.coverage.syntax_ingest_supported is True
    assert result.coverage.to_dict()["support_scope"] == (
        STRUCTURE_INGEST_SUPPORT_SCOPE
    )
    assert validate_all_atom_system(system).valid
    topology_digest = canonical_topology_sha256(system)
    assert result.coverage.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert result.coverage.canonical_topology_sha256 == topology_digest
    assert system.provenance.metadata["canonical_topology_schema_id"] == (
        CANONICAL_TOPOLOGY_SCHEMA_ID
    )
    assert system.provenance.metadata["canonical_topology_sha256"] == topology_digest
    assert attached_canonical_topology_sha256_matches(system)
    repeated = parse_mmcif(source)
    assert repeated.coverage.canonical_topology_sha256 == topology_digest
    restored = deserialize_all_atom_system(serialize_all_atom_system(system))
    assert canonical_all_atom_systems_equal(system, restored)
    assert canonical_topology_sha256(restored) == topology_digest
    assert attached_canonical_topology_sha256_matches(restored)


def test_mmcif_explicit_arbitrary_altloc_selection_and_official_auth_alt_preservation() -> None:
    headers = MMCIF_HEADERS + (
        "_atom_site.label_alt_id",
        "_atom_site.pdbx_auth_alt_id",
    )
    source = _mmcif(
        (
            "ATOM 1 N N GLY A 1 0.0 0.0 0.0 1 . .",
            "ATOM 2 C CA GLY A 1 1.0 0.0 0.0 1 conf-A auth-A",
            "ATOM 3 C CA GLY A 1 2.0 0.0 0.0 1 conf-B auth-B",
        ),
        headers=headers,
        data_name="altloc",
    )
    result = parse_mmcif(source, altloc_id="conf-A")
    system = result.system

    assert [(atom.name, atom.altloc) for atom in system.atoms] == [
        ("N", ""),
        ("CA", "conf-A"),
    ]
    assert system.atoms[1].metadata["mmcif"]["auth_identity"]["alt_id"] == (
        "auth-A"
    )
    assert result.coverage.source_atom_row_count == 3
    assert result.coverage.altloc_status == "explicit_id_selected"
    assert result.coverage.requested_altloc_id == "conf-A"
    assert result.coverage.altloc_kept_row_count == 2
    assert result.coverage.altloc_discarded_row_count == 1
    assert "select_explicit_altloc_id/v1" in system.provenance.operations
    assert attached_canonical_topology_sha256_matches(system)


def test_mmcif_auth_alt_id_is_preserved_but_never_used_as_selection_identity() -> None:
    headers = MMCIF_HEADERS + ("_atom_site.pdbx_auth_alt_id",)
    source = _mmcif(
        ("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1 author-A",),
        headers=headers,
        data_name="auth_alt_only",
    )
    result = parse_mmcif(source)
    assert result.system.atoms[0].altloc == ""
    assert result.system.atoms[0].metadata["mmcif"]["auth_identity"]["alt_id"] == (
        "author-A"
    )
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(source, altloc_id="author-A")
    assert exc_info.value.code == "requested_altloc_not_present"


def test_mmcif_altloc_selection_is_fixed_across_models_and_snapshot_stable() -> None:
    headers = MMCIF_HEADERS + ("_atom_site.label_alt_id",)
    source = _mmcif(
        (
            "ATOM 1 C CA GLY A 1 1.0 0.0 0.0 1 A",
            "ATOM 2 C CA GLY A 1 2.0 0.0 0.0 1 B",
            "ATOM 3 C CA GLY A 1 1.1 0.0 0.0 2 A",
            "ATOM 4 C CA GLY A 1 2.1 0.0 0.0 2 B",
        ),
        headers=headers,
        data_name="altloc_models",
    )
    first = parse_mmcif(source, altloc_id="B")
    second = parse_mmcif(source, altloc_id="B")
    assert first.system.coordinates.shape == (2, 1, 3)
    assert first.system.atoms[0].altloc == "B"
    assert torch.allclose(
        first.system.coordinates[:, 0, 0],
        torch.tensor([2.0, 2.1], dtype=torch.float64),
    )
    assert first.coverage.canonical_topology_sha256 == (
        second.coverage.canonical_topology_sha256
    )
    restored = deserialize_all_atom_system(serialize_all_atom_system(first.system))
    assert restored.atoms[0].altloc == "B"
    assert canonical_topology_sha256(restored) == (
        first.coverage.canonical_topology_sha256
    )
    assert attached_canonical_topology_sha256_matches(restored)

    mismatched = _mmcif(
        (
            "ATOM 1 C CA GLY A 1 1.0 0.0 0.0 1 A",
            "ATOM 2 C CA GLY A 1 2.0 0.0 0.0 1 B",
            "ATOM 3 C CA GLY A 1 1.1 0.0 0.0 2 A",
        ),
        headers=headers,
        data_name="altloc_model_mismatch",
    )
    with pytest.raises(StructureParseError) as mismatch_error:
        parse_mmcif(mismatched, altloc_id="A")
    assert mismatch_error.value.code == "model_altloc_inventory_mismatch"


def test_mmcif_altloc_candidates_must_match_and_requested_id_must_exist() -> None:
    headers = MMCIF_HEADERS + ("_atom_site.label_alt_id",)
    unequal = _mmcif(
        (
            "ATOM 1 C CA GLY A 1 1.0 0.0 0.0 1 A",
            "ATOM 2 C CB GLY A 1 2.0 0.0 0.0 1 B",
        ),
        headers=headers,
        data_name="altloc_unequal",
    )
    with pytest.raises(StructureParseError) as unequal_error:
        parse_mmcif(unequal, altloc_id="A")
    assert unequal_error.value.code == "inconsistent_altloc_atom_identity"

    equal = _mmcif(
        (
            "ATOM 1 C CA GLY A 1 1.0 0.0 0.0 1 A",
            "ATOM 2 C CA GLY A 1 2.0 0.0 0.0 1 B",
        ),
        headers=headers,
        data_name="altloc_missing",
    )
    with pytest.raises(StructureParseError) as missing_error:
        parse_mmcif(equal, altloc_id="C")
    assert missing_error.value.code == "requested_altloc_missing_for_residue"

    auth_headers = MMCIF_HEADERS + (
        "_atom_site.label_alt_id",
        "_atom_site.auth_atom_id",
    )
    conflicting_auth = _mmcif(
        (
            "ATOM 1 C CA GLY A 1 1.0 0.0 0.0 1 A AUTH_CA",
            "ATOM 2 C CA GLY A 1 2.0 0.0 0.0 1 B AUTH_CB",
        ),
        headers=auth_headers,
        data_name="altloc_auth_conflict",
    )
    with pytest.raises(StructureParseError) as auth_error:
        parse_mmcif(conflicting_auth, altloc_id="A")
    assert auth_error.value.code == "inconsistent_altloc_atom_identity"


def test_altloc_public_api_rejects_lossy_argument_coercion() -> None:
    pdb_source = _pdb(
        _pdb_atom("ATOM", 1, "CA", "GLY", "A", 1, 0.0, 0.0, 0.0, "C"),
        "END",
    )
    mmcif_source = _mmcif(("ATOM 1 C CA GLY A 1 0.0 0.0 0.0 1",))
    with pytest.raises(TypeError, match="altloc_id must be a string or None"):
        parse_pdb(pdb_source, altloc_id=1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="altloc_id must be a string or None"):
        parse_mmcif(mmcif_source, altloc_id=1)  # type: ignore[arg-type]


def test_parse_mmcif_auth_identity_insertion_charge_and_models() -> None:
    headers = MMCIF_HEADERS + (
        "_atom_site.auth_atom_id",
        "_atom_site.auth_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_seq_id",
        "_atom_site.pdbx_PDB_ins_code",
        "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        "_atom_site.pdbx_formal_charge",
    )
    rows = (
        "ATOM 1 N N ALA A 1 0.0 0.0 0.0 1 N ALA X 10 A 1.0 12.0 1",
        "ATOM 2 C CA ALA A 1 1.4 0.0 0.0 1 CA ALA X 10 A 1.0 13.0 0",
        "ATOM 3 N N ALA A 1 0.1 0.0 0.0 2 N ALA X 10 A 1.0 12.0 1",
        "ATOM 4 C CA ALA A 1 1.5 0.0 0.0 2 CA ALA X 10 A 1.0 13.0 0",
    )
    result = parse_mmcif(_mmcif(rows, headers=headers, data_name="multi"))
    system = result.system
    assert system.model_count == 2
    assert system.chains[0].chain_id == "A"
    assert system.chains[0].metadata["auth_asym_ids"] == ["X"]
    assert system.residues[0].sequence_number == 1
    assert system.residues[0].insertion_code == "A"
    assert system.atoms[0].formal_charge == 1
    assert system.atoms[0].metadata["formal_charge_source"] == (
        "_atom_site.pdbx_formal_charge"
    )
    assert system.atoms[0].metadata["hydrogen_origin"] == "not_hydrogen"
    assert system.atoms[0].occupancy == 1.0
    assert torch.allclose(system.coordinates[:, 0, 0], torch.tensor([0.0, 0.1], dtype=torch.float64))


def test_mmcif_explicit_hydrogen_is_source_observed_not_completion() -> None:
    result = parse_mmcif(
        _mmcif(("ATOM 1 H H GLY A 1 0.0 0.0 0.0 1",))
    )
    atom = result.system.atoms[0]
    assert atom.metadata["hydrogen_origin"] == "source"
    assert atom.formal_charge_known is False
    assert atom.metadata["formal_charge_source"] == "missing_in_mmcif"


def test_mmcif_raw_formal_charge_token_is_bound_to_parser_observation() -> None:
    source = parse_mmcif(
        _mmcif(
            ("ATOM 1 N N LIG A 1 0.0 0.0 0.0 1 1",),
            headers=MMCIF_HEADERS
            + ("_atom_site.pdbx_formal_charge",),
        )
    ).system
    assert source.atoms[0].formal_charge == 1
    assert attached_parser_observation_sha256_matches(source)

    atom_metadata = dict(source.atoms[0].metadata)
    mmcif_metadata = dict(atom_metadata["mmcif"])
    atom_site = dict(mmcif_metadata["atom_site"])
    atom_site.pop("_atom_site.pdbx_formal_charge")
    mmcif_metadata["atom_site"] = atom_site
    atom_metadata["mmcif"] = mmcif_metadata
    forged = replace(
        source,
        atoms=(replace(source.atoms[0], metadata=atom_metadata),),
    )
    assert attached_parser_observation_sha256_matches(forged) is False
    report = analyze_molecular_preparation(forged)
    assert report.parser_observation_self_consistent is False
    assert report.formal_charge_origin_counts == (
        ("unclassified_known", 1),
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff\xfe", "invalid_utf8"),
        (b"loop_\n_atom_site.id\n1\n", "missing_data_block"),
        (_mmcif(("ATOM 1 C CA ALA A 1 0.0 0.0",)), "malformed_loop_rows"),
        (
            _mmcif(
                ("ATOM 1 C CA ALA A 1 0.0 0.0 0.0 1 A",),
                headers=MMCIF_HEADERS + ("_atom_site.label_alt_id",),
            ),
            "unsupported_altloc",
        ),
        (_mmcif(("ATOM 1 Xx CA ALA A 1 0.0 0.0 0.0 1",)), "unknown_element"),
        (
            _mmcif(
                (
                    "ATOM 1 C CA ALA A 9007199254740992 "
                    "0.0 0.0 0.0 1",
                )
            ),
            "invalid_residue_number",
        ),
        (
            _mmcif(
                ("ATOM 1 C CA ALA A 1 0.0 0.0 0.0 1 32768",),
                headers=MMCIF_HEADERS
                + ("_atom_site.pdbx_formal_charge",),
            ),
            "invalid_formal_charge",
        ),
        (_mmcif(("ATOM 1 C CA ALA A 1 1_0.0 0.0 0.0 1",)), "invalid_atom_coordinate"),
        (
            _mmcif(
                ("ATOM 1 C CA ALA A 1 0.0 0.0 0.0 1",),
                headers=("_other.group",) + MMCIF_HEADERS[1:],
            ),
            "mixed_atom_site_loop",
        ),
        (
            _mmcif(
                (
                    "ATOM 1 C CA ALA A 1 0.0 0.0 0.0 1",
                    "ATOM 2 C CB ALA A 1 0.1 0.0 0.0 2",
                )
            ),
            "model_topology_mismatch",
        ),
        (b"data_x\nloop_\n_atom_site.id\n'unclosed\n", "unterminated_quoted_value"),
    ],
)
def test_mmcif_failure_corpus(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(payload)
    assert exc_info.value.source_format == "mmcif"
    assert exc_info.value.code == code


def test_mmcif_large_leading_zero_integer_is_normalized_without_raw_int_error() -> None:
    padded_one = "0" * 1900 + "1"
    result = parse_mmcif(
        _mmcif(
            (
                f"ATOM 1 C CA ALA A {padded_one} "
                "0.0 0.0 0.0 1",
            )
        )
    )
    assert result.system.residues[0].sequence_number == 1


def test_coordinate_parsers_reject_wrong_argument_types() -> None:
    with pytest.raises(TypeError, match="PDB input must be bytes"):
        parse_pdb("not-bytes")
    with pytest.raises(TypeError, match="mmCIF input must be bytes"):
        parse_mmcif("not-bytes")
    with pytest.raises(TypeError, match="source_id must be a string"):
        parse_pdb(_pdb(_pdb_atom("ATOM", 1, "N", "GLY", "A", 1, 0, 0, 0, "N")), source_id=1)
    with pytest.raises(TypeError, match="source_id must be a string"):
        parse_mmcif(_mmcif(("ATOM 1 C CA ALA A 1 0.0 0.0 0.0 1",)), source_id=1)
