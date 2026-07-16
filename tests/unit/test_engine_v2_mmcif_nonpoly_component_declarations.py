from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_declarations import (
    CHEM_COMP_ATOM_CATEGORY,
    CHEM_COMP_BOND_CATEGORY,
    MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
    MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID,
    MmcifNonpolyComponentDeclarationError,
    mmcif_nonpoly_component_declaration_document,
    mmcif_nonpoly_component_declaration_json_bytes,
    parse_mmcif_nonpoly_component_declarations,
    require_mmcif_nonpoly_component_declaration_document,
    write_mmcif_nonpoly_component_declaration_json,
)


ENTITY_HEADERS = ("_entity.id", "_entity.type")
ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
    "_chem_comp.pdbx_formal_charge",
)
ENTITY_NONPOLY_HEADERS = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.name",
    "_pdbx_entity_nonpoly.comp_id",
)
SCHEME_HEADERS = (
    "_pdbx_nonpoly_scheme.asym_id",
    "_pdbx_nonpoly_scheme.entity_id",
    "_pdbx_nonpoly_scheme.mon_id",
    "_pdbx_nonpoly_scheme.ndb_seq_num",
    "_pdbx_nonpoly_scheme.pdb_seq_num",
    "_pdbx_nonpoly_scheme.auth_seq_num",
    "_pdbx_nonpoly_scheme.pdb_mon_id",
    "_pdbx_nonpoly_scheme.auth_mon_id",
    "_pdbx_nonpoly_scheme.pdb_strand_id",
    "_pdbx_nonpoly_scheme.pdb_ins_code",
)

ENTITY_ROWS = (
    {"_entity.id": "1", "_entity.type": "non-polymer"},
    {"_entity.id": "2", "_entity.type": "water"},
)
ASYM_ROWS = (
    {"_struct_asym.id": "L", "_struct_asym.entity_id": "1"},
    {"_struct_asym.id": "W", "_struct_asym.entity_id": "2"},
)
CHEM_COMP_ROWS = (
    {
        "_chem_comp.id": "ALA",
        "_chem_comp.type": "'L-peptide linking'",
        "_chem_comp.pdbx_formal_charge": "0",
    },
    {
        "_chem_comp.id": "LIG",
        "_chem_comp.type": "non-polymer",
        "_chem_comp.pdbx_formal_charge": "0",
    },
    {
        "_chem_comp.id": "HOH",
        "_chem_comp.type": "water",
        "_chem_comp.pdbx_formal_charge": "0",
    },
)
ENTITY_NONPOLY_ROWS = (
    {
        "_pdbx_entity_nonpoly.entity_id": "1",
        "_pdbx_entity_nonpoly.name": "'Opaque ligand source name'",
        "_pdbx_entity_nonpoly.comp_id": "LIG",
    },
    {
        "_pdbx_entity_nonpoly.entity_id": "2",
        "_pdbx_entity_nonpoly.name": "water",
        "_pdbx_entity_nonpoly.comp_id": "HOH",
    },
)
SCHEME_ROWS = (
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "1",
        "_pdbx_nonpoly_scheme.mon_id": "LIG",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "501",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-L",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "LIG",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHL",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "LX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": ".",
    },
    {
        "_pdbx_nonpoly_scheme.asym_id": "W",
        "_pdbx_nonpoly_scheme.entity_id": "2",
        "_pdbx_nonpoly_scheme.mon_id": "HOH",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "601",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-W",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "HOH",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHW",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "WX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
    },
)

ATOM_ROWS = (
    {
        "_chem_comp_atom.comp_id": "ALA",
        "_chem_comp_atom.atom_id": "CA",
        "_chem_comp_atom.type_symbol": "C",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "C1",
        "_chem_comp_atom.type_symbol": "C",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "O1",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "'?'",
        "_chem_comp_atom.pdbx_aromatic_flag": "Y",
        "_chem_comp_atom.pdbx_stereo_config": ".",
        "_chem_comp_atom.pdbx_ordinal": "2",
    },
    {
        "_chem_comp_atom.comp_id": "HOH",
        "_chem_comp_atom.atom_id": "O",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "?",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "'?'",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
)
BOND_ROWS = (
    {
        "_chem_comp_bond.comp_id": "ALA",
        "_chem_comp_bond.atom_id_1": "CA",
        "_chem_comp_bond.atom_id_2": "CB",
        "_chem_comp_bond.value_order": "SING",
        "_chem_comp_bond.pdbx_aromatic_flag": "N",
        "_chem_comp_bond.pdbx_stereo_config": "N",
        "_chem_comp_bond.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_bond.comp_id": "LIG",
        "_chem_comp_bond.atom_id_1": "C1",
        "_chem_comp_bond.atom_id_2": "O1",
        "_chem_comp_bond.value_order": "DOUB",
        "_chem_comp_bond.pdbx_aromatic_flag": "'?'",
        "_chem_comp_bond.pdbx_stereo_config": ".",
        "_chem_comp_bond.pdbx_ordinal": "1",
    },
)

UNINTERPRETED_TAIL = """loop_
_atom_site.id
_atom_site.occupancy
1 0.50
#
_audit_conform.dict_name SOURCE_ONLY
"""


def _loop(
    headers: tuple[str, ...],
    rows: tuple[dict[str, str], ...],
) -> str:
    assert rows
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _source(
    *,
    atom_rows: tuple[dict[str, str], ...] | None = ATOM_ROWS,
    bond_rows: tuple[dict[str, str], ...] | None = BOND_ROWS,
    atom_headers: tuple[str, ...] = MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
    bond_headers: tuple[str, ...] = MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
    tail: str = UNINTERPRETED_TAIL,
) -> str:
    source = (
        "data_component_declarations\n#\n"
        + _loop(ENTITY_HEADERS, ENTITY_ROWS)
        + _loop(ASYM_HEADERS, ASYM_ROWS)
        + _loop(CHEM_COMP_HEADERS, CHEM_COMP_ROWS)
        + _loop(ENTITY_NONPOLY_HEADERS, ENTITY_NONPOLY_ROWS)
        + _loop(SCHEME_HEADERS, SCHEME_ROWS)
    )
    if atom_rows is not None:
        source += _loop(atom_headers, atom_rows)
    if bond_rows is not None:
        source += _loop(bond_headers, bond_rows)
    return source + tail


def _updated(
    rows: tuple[dict[str, str], ...],
    row_index: int,
    field: str,
    value: str,
) -> tuple[dict[str, str], ...]:
    copied = [dict(row) for row in rows]
    copied[row_index][field] = value
    return tuple(copied)


def _error(source: str, code: str) -> MmcifNonpolyComponentDeclarationError:
    with pytest.raises(MmcifNonpolyComponentDeclarationError) as exc_info:
        parse_mmcif_nonpoly_component_declarations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_preserves_selected_atom_and_bond_source_tokens() -> None:
    source = _source()
    snapshot = parse_mmcif_nonpoly_component_declarations(source)

    assert snapshot.source_sha256 == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert snapshot.component_ids == ("LIG", "HOH")
    assert [(row.comp_id, row.atom_id, row.ordinal) for row in snapshot.atom_declarations] == [
        ("LIG", "C1", 1),
        ("LIG", "O1", 2),
        ("HOH", "O", 1),
    ]
    assert len(snapshot.bond_declarations) == 1
    bond = snapshot.bond_declarations[0]
    assert (bond.comp_id, bond.atom_id_1, bond.atom_id_2, bond.ordinal) == (
        "LIG",
        "C1",
        "O1",
        1,
    )
    oxygen = snapshot.atom_declarations[1]
    water = snapshot.atom_declarations[2]
    assert oxygen.charge.state == "known"
    assert oxygen.charge.value == "?"
    assert oxygen.charge.quoted is True
    assert oxygen.aromatic_flag.value == "Y"
    assert oxygen.stereo_config.state == "not_applicable"
    assert water.charge.state == "unknown"
    assert water.stereo_config.state == "known"
    assert water.stereo_config.value == "?"
    assert water.stereo_config.quoted is True
    assert bond.value_order.value == "DOUB"
    assert bond.aromatic_flag.state == "known"
    assert bond.aromatic_flag.value == "?"
    assert bond.aromatic_flag.quoted is True
    assert bond.stereo_config.state == "not_applicable"
    assert snapshot.bond_category_present is True
    assert snapshot.uninterpreted_categories == ("_atom_site", "_audit_conform")

    bindings = {row.category: row for row in snapshot.category_bindings}
    atom_binding = bindings[CHEM_COMP_ATOM_CATEGORY]
    assert atom_binding.selected_row_count == 3
    assert atom_binding.row_count == 4
    assert atom_binding.interpreted_headers == (
        "_chem_comp_atom.comp_id",
        "_chem_comp_atom.atom_id",
        "_chem_comp_atom.pdbx_ordinal",
    )
    assert atom_binding.uninterpreted_headers == (
        "_chem_comp_atom.type_symbol",
        "_chem_comp_atom.charge",
        "_chem_comp_atom.pdbx_aromatic_flag",
        "_chem_comp_atom.pdbx_stereo_config",
    )
    assert bindings[CHEM_COMP_BOND_CATEGORY].selected_row_count == 1

    payload = snapshot.to_dict()
    assert payload["profile_id"] == MMCIF_NONPOLY_COMPONENT_DECLARATION_PROFILE_ID
    assert payload["component_atom_counts"] == {"LIG": 2, "HOH": 1}
    assert payload["component_bond_counts"] == {"LIG": 1, "HOH": 0}
    assert payload["source_component_atom_declarations_preserved"] is True
    assert payload["source_component_bond_declarations_preserved"] is True
    assert payload["component_identity_references_verified"] is True
    assert payload["bond_endpoint_identity_references_verified"] is True
    for flag in (
        "source_authenticated",
        "atom_site_identity_joined",
        "coordinates_interpreted",
        "type_symbol_interpreted",
        "atom_charge_interpreted",
        "aromaticity_interpreted",
        "stereo_interpreted",
        "bond_order_interpreted",
        "bond_topology_interpreted",
        "component_chemistry_interpreted",
        "role_assignment_interpreted",
        "coordination_interpreted",
        "charge_interpreted",
        "protonation_interpreted",
        "preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_eligible",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_header_order_changes_source_binding_not_declaration_projection() -> None:
    canonical = parse_mmcif_nonpoly_component_declarations(_source())
    reordered = parse_mmcif_nonpoly_component_declarations(
        _source(
            atom_headers=tuple(reversed(MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS)),
            bond_headers=tuple(reversed(MMCIF_NONPOLY_COMPONENT_BOND_HEADERS)),
        )
    )

    assert canonical.declaration_projection_sha256 == reordered.declaration_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256


def test_selected_source_token_changes_projection_but_unselected_changes_only_binding() -> None:
    selected = parse_mmcif_nonpoly_component_declarations(
        _source(
            atom_rows=_updated(ATOM_ROWS, 1, "_chem_comp_atom.charge", "+9"),
        )
    )
    unselected = parse_mmcif_nonpoly_component_declarations(
        _source(
            atom_rows=_updated(ATOM_ROWS, 0, "_chem_comp_atom.charge", "PRIVATE"),
        )
    )
    canonical = parse_mmcif_nonpoly_component_declarations(_source())

    assert canonical.declaration_projection_sha256 != selected.declaration_projection_sha256
    assert canonical.declaration_projection_sha256 == unselected.declaration_projection_sha256
    assert canonical.source_binding_sha256 != unselected.source_binding_sha256


def test_source_row_order_is_preserved() -> None:
    canonical = parse_mmcif_nonpoly_component_declarations(_source())
    reordered_rows = (ATOM_ROWS[0], ATOM_ROWS[3], ATOM_ROWS[1], ATOM_ROWS[2])
    reordered = parse_mmcif_nonpoly_component_declarations(
        _source(atom_rows=reordered_rows)
    )

    assert [row.atom_id for row in canonical.atom_declarations] == ["C1", "O1", "O"]
    assert [row.atom_id for row in reordered.atom_declarations] == ["O", "C1", "O1"]
    assert canonical.declaration_projection_sha256 != reordered.declaration_projection_sha256


def test_bond_category_is_optional_and_absence_is_bound() -> None:
    snapshot = parse_mmcif_nonpoly_component_declarations(_source(bond_rows=None))

    assert snapshot.bond_category_present is False
    assert snapshot.bond_declarations == ()
    assert [row.category for row in snapshot.category_bindings] == [
        CHEM_COMP_ATOM_CATEGORY
    ]
    assert snapshot.to_dict()["component_bond_counts"] == {"LIG": 0, "HOH": 0}


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_component_declarations(_source())
    document = mmcif_nonpoly_component_declaration_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_COMPONENT_DECLARATION_DOCUMENT_SCHEMA_ID
    assert require_mmcif_nonpoly_component_declaration_document(document) == document
    encoded = mmcif_nonpoly_component_declaration_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_component_declaration_json(
        tmp_path / "component-declarations.json",
        snapshot,
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".component-declarations.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["declaration_projection"]["atom_declarations"][0]["atom_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_nonpoly_component_declaration_document(tampered)


def test_missing_scalar_mixed_and_header_surfaces_fail_closed() -> None:
    _error(_source(atom_rows=None), "required_category_missing")

    scalar = _source(atom_rows=None) + "_chem_comp_atom.comp_id LIG\n"
    _error(scalar, "category_must_be_loop")

    mixed_headers = MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS + ("_custom.value",)
    mixed_rows = tuple({**row, "_custom.value": "x"} for row in ATOM_ROWS)
    _error(
        _source(atom_rows=mixed_rows, atom_headers=mixed_headers),
        "mixed_category_loop",
    )

    missing_header = tuple(
        header
        for header in MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS
        if header != "_chem_comp_atom.charge"
    )
    _error(
        _source(atom_headers=missing_header),
        "unsupported_headers",
    )


def test_selected_component_atom_coverage_is_required() -> None:
    only_ligand = tuple(row for row in ATOM_ROWS if row["_chem_comp_atom.comp_id"] != "HOH")
    _error(
        _source(atom_rows=only_ligand),
        "component_atom_coverage_mismatch",
    )


def test_duplicate_atom_identity_and_ordinal_are_rejected() -> None:
    duplicate_id = dict(ATOM_ROWS[1])
    duplicate_id["_chem_comp_atom.pdbx_ordinal"] = "3"
    _error(
        _source(atom_rows=ATOM_ROWS + (duplicate_id,)),
        "duplicate_component_atom_id",
    )

    duplicate_ordinal = dict(ATOM_ROWS[1])
    duplicate_ordinal["_chem_comp_atom.atom_id"] = "C2"
    _error(
        _source(atom_rows=ATOM_ROWS + (duplicate_ordinal,)),
        "duplicate_component_atom_ordinal",
    )


def test_bond_endpoint_self_pair_and_duplicates_are_rejected() -> None:
    missing_endpoint = _updated(BOND_ROWS, 1, "_chem_comp_bond.atom_id_2", "PRIVATE")
    _error(
        _source(bond_rows=missing_endpoint),
        "bond_endpoint_identity_missing",
    )

    self_pair = _updated(BOND_ROWS, 1, "_chem_comp_bond.atom_id_2", "C1")
    _error(
        _source(bond_rows=self_pair),
        "self_component_bond_declaration",
    )

    reverse = dict(BOND_ROWS[1])
    reverse["_chem_comp_bond.atom_id_1"] = "O1"
    reverse["_chem_comp_bond.atom_id_2"] = "C1"
    reverse["_chem_comp_bond.pdbx_ordinal"] = "2"
    _error(
        _source(bond_rows=BOND_ROWS + (reverse,)),
        "duplicate_component_bond_pair",
    )

    duplicate_ordinal = dict(BOND_ROWS[1])
    duplicate_ordinal["_chem_comp_bond.atom_id_1"] = "C1"
    duplicate_ordinal["_chem_comp_bond.atom_id_2"] = "C2"
    _error(
        _source(
            atom_rows=ATOM_ROWS
            + (
                {
                    "_chem_comp_atom.comp_id": "LIG",
                    "_chem_comp_atom.atom_id": "C2",
                    "_chem_comp_atom.type_symbol": "C",
                    "_chem_comp_atom.charge": "0",
                    "_chem_comp_atom.pdbx_aromatic_flag": "N",
                    "_chem_comp_atom.pdbx_stereo_config": "N",
                    "_chem_comp_atom.pdbx_ordinal": "3",
                },
            ),
            bond_rows=BOND_ROWS + (duplicate_ordinal,),
        ),
        "duplicate_component_bond_ordinal",
    )


def test_identity_marker_integer_and_token_bounds_are_enforced() -> None:
    quoted_atom = _updated(ATOM_ROWS, 1, "_chem_comp_atom.atom_id", "'C1'")
    _error(_source(atom_rows=quoted_atom), "invalid_identity_token")

    invalid_ordinal = _updated(ATOM_ROWS, 1, "_chem_comp_atom.pdbx_ordinal", "01")
    _error(_source(atom_rows=invalid_ordinal), "invalid_positive_integer")

    huge_ordinal = _updated(
        ATOM_ROWS,
        1,
        "_chem_comp_atom.pdbx_ordinal",
        str(1 << 53),
    )
    _error(_source(atom_rows=huge_ordinal), "positive_integer_out_of_bounds")

    long_token = "'" + ("X" * 257) + "'"
    oversized = _updated(ATOM_ROWS, 0, "_chem_comp_atom.charge", long_token)
    _error(_source(atom_rows=oversized), "source_token_out_of_bounds")


def test_errors_do_not_echo_private_identity_values() -> None:
    private = _updated(ATOM_ROWS, 1, "_chem_comp_atom.comp_id", "PRIVATE-COMP")
    error = _error(_source(atom_rows=private), "component_atom_coverage_mismatch")

    assert "PRIVATE-COMP" not in str(error)
    assert "PRIVATE-COMP" not in error.detail


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_component_declarations(b"data_x")  # type: ignore[arg-type]
